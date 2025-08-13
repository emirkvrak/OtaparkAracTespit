
import os
import json
import cv2
import numpy as np
import psycopg2
import psycopg2.extras as extras
from dotenv import load_dotenv

load_dotenv()  # .env yoksa sorun değil, os.getenv yine çalışır

DB_NAME = os.getenv("POSTGRES_DB", "DigitalImageProcessing")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5430")

# PostgreSQL bağlantısı
try:
    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
    )
    cursor = conn.cursor()
    # Şema: JSONB kullanalım
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Blocks (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ParkingAreas (
            id SERIAL PRIMARY KEY,
            block_id INTEGER REFERENCES Blocks(id) ON DELETE CASCADE,
            area_number INTEGER,
            is_full BOOLEAN DEFAULT FALSE,
            points JSONB
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS EntryExitRecords (
            id SERIAL PRIMARY KEY,
            parking_area_id INTEGER REFERENCES ParkingAreas(id) ON DELETE CASCADE,
            entry_time TIMESTAMPTZ,
            exit_time TIMESTAMPTZ
        );
    """)
    conn.commit()
except psycopg2.Error as e:
    print("Veritabanı bağlantı hatası:", e)
    raise SystemExit(1)

areas = []
points = []
frame = None

def delete_area(x, y):
    global areas
    for i, area in enumerate(areas):
        rect = cv2.boundingRect(np.array(area['points']))
        x1, y1, w, h = rect
        x2, y2 = x1 + w, y1 + h
        if x1 <= x <= x2 and y1 <= y <= y2:
            cursor.execute("DELETE FROM EntryExitRecords WHERE parking_area_id = %s", (area['id'],))
            cursor.execute("DELETE FROM ParkingAreas WHERE id = %s", (area['id'],))
            conn.commit()
            del areas[i]
            break

def add_area():
    global points
    if len(points) != 4:
        print("Dikdörtgen tanımlamak için 4 noktaya ihtiyacınız var.")
        return

    block_name = input("Blok adını girin (ör. A, B ...): ").strip().upper()
    area_number = int(input("Alan numarasını girin (pozitif tamsayı): ").strip())

    # Aynı blok ve alan var mı?
    cursor.execute("""
        SELECT COUNT(*)
        FROM ParkingAreas pa
        JOIN Blocks b ON pa.block_id = b.id
        WHERE b.name = %s AND pa.area_number = %s
    """, (block_name, area_number))
    if cursor.fetchone()[0] > 0:
        print("Bu blok adı ve alan numarası zaten var.")
        points = []
        return

    # Block ekle veya id al
    cursor.execute("INSERT INTO Blocks (name) VALUES (%s) ON CONFLICT DO NOTHING RETURNING id", (block_name,))
    res = cursor.fetchone()
    if res is None:
        cursor.execute("SELECT id FROM Blocks WHERE name = %s", (block_name,))
        block_id = cursor.fetchone()[0]
    else:
        block_id = res[0]

    # points -> JSONB
    pts_json = extras.Json(points)  # [(x,y),...] şeklindeki listeyi JSON olarak yazar
    cursor.execute("""
        INSERT INTO ParkingAreas (block_id, area_number, points)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (block_id, area_number, pts_json))
    area_id = cursor.fetchone()[0]
    conn.commit()

    areas.append({'id': area_id, 'points': points.copy(), 'area_number': area_number, 'block_name': block_name})
    points = []

def show_areas(frame):
    global areas
    areas = []
    cursor.execute("""
        SELECT pa.id, pa.points, pa.area_number, b.name
        FROM ParkingAreas pa
        JOIN Blocks b ON pa.block_id = b.id
    """)
    for area_id, points_json, area_number, block_name in cursor.fetchall():
        pts = points_json if isinstance(points_json, list) else json.loads(points_json)
        areas.append({'id': area_id, 'points': pts, 'area_number': area_number, 'block_name': block_name})
        cv2.polylines(frame, [np.array(pts, np.int32)], True, (0, 255, 0), 2)
        cv2.putText(frame, f"{block_name}-{area_number}", tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

def draw_area(event, x, y, flags, param):
    global points, frame
    if event == cv2.EVENT_LBUTTONDOWN:
        if len(points) < 4:
            points.append((x, y))
        if len(points) == 4:
            frame_copy = frame.copy()
            cv2.polylines(frame_copy, [np.array(points, np.int32)], True, (0, 255, 0), 2)
            cv2.imshow('FRAME', frame_copy)
            add_area()
    elif event == cv2.EVENT_RBUTTONDOWN:
        delete_area(x, y)

cv2.namedWindow('FRAME', cv2.WINDOW_NORMAL)
cv2.setMouseCallback('FRAME', draw_area)

cap = cv2.VideoCapture('video.mp4')

while True:
    ret, frame = cap.read()
    if not ret:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue
    frame = cv2.resize(frame, (1800, 900))
    show_areas(frame)
    cv2.imshow('FRAME', frame)
    k = cv2.waitKey(1) & 0xFF
    if k == ord('q'):
        break
    if k == ord('s'):
        conn.commit()

cursor.close()
conn.close()
cap.release()
cv2.destroyAllWindows()
