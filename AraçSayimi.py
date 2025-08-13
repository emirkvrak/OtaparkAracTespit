import os
import json
import cv2
import pandas as pd
import numpy as np
import psycopg2
from datetime import datetime, timezone
from ultralytics import YOLO
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv("POSTGRES_DB", "DigitalImageProcessing")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5430")

# Sınıf isimleri
with open("nesne.txt", "r", encoding="utf-8") as f:
    class_list = [line.strip() for line in f if line.strip()]

# DB bağlantısı
try:
    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
    )
    cursor = conn.cursor()

    cursor.execute("SELECT id, points, (SELECT name FROM Blocks b WHERE b.id = block_id) AS block_name, area_number FROM ParkingAreas")
    rows = cursor.fetchall()

    areas = []
    for area_id, points_json, block_name, area_number in rows:
        pts = points_json if isinstance(points_json, list) else json.loads(points_json)
        areas.append({"id": area_id, "points": pts, "block_name": block_name, "area_number": area_number})

    parking_status = {f"{a['block_name']} - {a['area_number']}": 'empty' for a in areas}

except psycopg2.Error as e:
    print("Veritabanı hatası:", e)
    raise SystemExit(1)

model = YOLO('yolov8s.pt')

cap = cv2.VideoCapture('video.mp4')
cv2.namedWindow('FRAME', cv2.WINDOW_NORMAL)

frame_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    frame_count += 1
    if frame_count % 3 != 0:
        continue

    frame = cv2.resize(frame, (1800, 900))
    results = model.predict(frame, verbose=False)
    detections = results[0].boxes.data
    px = pd.DataFrame(detections).astype("float")

    centers = []
    for _, row in px.iterrows():
        x1, y1, x2, y2, _, cls_idx = map(int, [row[0], row[1], row[2], row[3], row[4], row[5]])
        c = class_list[cls_idx] if 0 <= cls_idx < len(class_list) else "unknown"
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        # >>> BUGFIX: yalnızca bu sınıflar sayılır
        if c in ("car", "bus", "truck"):
            centers.append((cx, cy))
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)
            cv2.putText(frame, c, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

    occupied_count = 0

    for area in areas:
        pts = np.array(area['points'], np.int32).reshape((-1, 1, 2))
        cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
        cv2.putText(frame, f"{area['block_name']} - {area['area_number']}", tuple(pts[0][0]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

        area_key = f"{area['block_name']} - {area['area_number']}"
        is_inside = False

        for (cx, cy) in centers:
            if cv2.pointPolygonTest(pts, (cx, cy), False) >= 0:
                is_inside = True
                cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)
                cv2.polylines(frame, [pts], True, (0, 0, 255), 2)
                break

        now = datetime.now(timezone.utc)

        if is_inside:
            if parking_status[area_key] == 'empty':
                cursor.execute(
                    "INSERT INTO EntryExitRecords (parking_area_id, entry_time) VALUES (%s, %s)",
                    (area['id'], now)
                )
                cursor.execute("UPDATE ParkingAreas SET is_full = TRUE WHERE id = %s", (area['id'],))
                conn.commit()
                parking_status[area_key] = 'occupied'
            occupied_count += 1
        else:
            if parking_status[area_key] == 'occupied':
                cursor.execute(
                    "UPDATE EntryExitRecords SET exit_time = %s WHERE parking_area_id = %s AND exit_time IS NULL",
                    (now, area['id'])
                )
                cursor.execute("UPDATE ParkingAreas SET is_full = FALSE WHERE id = %s", (area['id'],))
                conn.commit()
                parking_status[area_key] = 'empty'

    empty_count = len(areas) - occupied_count
    h, w, _ = frame.shape
    cv2.putText(frame, f'Bos Alan: {empty_count}', (w - 220, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
    cv2.putText(frame, f'Toplam Arac: {occupied_count}', (w - 220, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)

    # Alan bazlı son giriş/çıkış
    for i, area in enumerate(areas):
        area_key = f"{area['block_name']} - {area['area_number']}"
        cursor.execute("""
            SELECT entry_time, exit_time
            FROM EntryExitRecords
            WHERE parking_area_id = %s
            ORDER BY entry_time DESC
            LIMIT 1
        """, (area['id'],))
        row = cursor.fetchone()
        if row:
            entry_time = row[0].astimezone(timezone.utc).strftime("%H:%M-%d/%m/%Y") if row[0] else "-"
            exit_time = row[1].astimezone(timezone.utc).strftime("%H:%M-%d/%m/%Y") if row[1] else "-"
            status = "Dolu" if parking_status[area_key] == "occupied" else "Bos"
            text = f'{area_key}: {status}  Giris:{entry_time}  Cikis:{exit_time if exit_time!="-" else "-"}'
        else:
            text = f'{area_key}: Bos'

        cv2.putText(frame, text, (10, 30 + 22*i), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 2)

    cv2.imshow('FRAME', frame)
    if (cv2.waitKey(1) & 0xFF) == ord('q'):
        break

cap.release()
cursor.close()
conn.close()
cv2.destroyAllWindows()
