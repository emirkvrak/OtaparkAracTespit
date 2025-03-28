
import cv2
import pandas as pd
import numpy as np
import psycopg2
import json
from datetime import datetime
from ultralytics import YOLO


# YOLO modelinin çıktı sınıflarını tanımla
my_file = open("nesne.txt", "r")
data = my_file.read()
class_list = data.split("\n")

try:
    conn = psycopg2.connect(
        dbname="OtaparkVerileri",
        user="postgres",
        password="846203",
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor()

    cursor.execute("SELECT id, points, block_id, area_number FROM ParkingAreas")
    rows = cursor.fetchall()
    areas = []
    
    for row in rows:
        area_id = row[0]
        points_text = row[1]
        if not points_text:
            print("Boş points_text değeri!")
            continue
        # JSON formatındaki veriyi çözümle
        points = json.loads(points_text.replace('{', '[').replace('}', ']'))
        block_id = row[2]
        area_number = row[3]

        # Blok adını almak için Blocks tablosundan sorgu yap
        cursor.execute("SELECT name FROM Blocks WHERE id = %s", (block_id,))
        block_name = cursor.fetchone()[0]

        areas.append({"id": area_id, "points": points, "block_name": block_name, "area_number": area_number})

    parking_status = {area['block_name'] + ' - ' + str(area['area_number']): 'empty' for area in areas}

except psycopg2.Error as e:
    print("Veritabanından veri çekerken bir hata oluştu:", e)
    exit()

model = YOLO('yolov8s.pt')

cap = cv2.VideoCapture('video.mp4')
cv2.namedWindow('FRAME', cv2.WINDOW_NORMAL)  # Pencereyi normal boyutta oluştur

count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    count += 1
    if count % 3 != 0:
        continue
    
    frame = cv2.resize(frame,(1800, 900))  # Video boyutunu 1800x900 olarak ayarla
    results = model.predict(frame)
    a = results[0].boxes.data
    px = pd.DataFrame(a).astype("float")

    list1 = []

    for index, row in px.iterrows():
        x1 = int(row[0])
        y1 = int(row[1])
        x2 = int(row[2])
        y2 = int(row[3])
        d = int(row[5])

        c = class_list[d] if 0 <= d < len(class_list) else "Unknown"
        cx = int(x1 + x2) // 2
        cy = int(y1 + y2) // 2
        if 'car' or 'bus' or 'truck' in c:
            list1.append([cx, cy])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)  # Araç çerçevesini beyaz olarak göster
            cv2.putText(frame, c, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)  # Araç türünü beyaz olarak göster

    occupied_count = 0
    
    for area in areas:
        rect = np.array(area['points'])
        pts = np.array(rect, np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
        cv2.putText(frame, f'{area["block_name"]} - {area["area_number"]}', tuple(pts[0][0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        area_key = area['block_name'] + ' - ' + str(area['area_number'])
        for cx1, cy1 in list1:
            if cv2.pointPolygonTest(pts, (cx1, cy1), False) >= 0:
                cv2.circle(frame, (cx1, cy1), 5, (255, 0, 0), -1)
                cv2.polylines(frame, [pts], True, (0, 0, 255), 2)
               
                # Eğer alan daha önce boşsa ve araç girmişse giriş zamanını kaydet
                if parking_status[area_key] == 'empty':
                    entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S%z")
                    cursor.execute(
                        "INSERT INTO EntryExitRecords (parking_area_id, entry_time) VALUES (%s, %s)",
                        (area['id'], entry_time)
                    )
                    conn.commit()
                    cursor.execute(
                        "UPDATE ParkingAreas SET is_full = TRUE WHERE id = %s",
                        (area['id'],)
                    )
                    conn.commit()
                    parking_status[area_key] = 'occupied'
                    

                occupied_count += 1  
                break
        else:
            # Eğer alan daha önce doluysa ve araç çıkmışsa çıkış zamanını kaydet
            if parking_status[area_key] == 'occupied':
                exit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S%z")
                cursor.execute(
                    "UPDATE EntryExitRecords SET exit_time = %s WHERE parking_area_id = %s AND exit_time IS NULL",
                    (exit_time, area['id'])
                )
                conn.commit()
                cursor.execute(
                    "UPDATE ParkingAreas SET is_full = FALSE WHERE id = %s",
                    (area['id'],)
                )
                conn.commit()
                parking_status[area_key] = 'empty'
                occupied_count -= 1
                
    empty_count = len(areas) - occupied_count            
    height, width, _ = frame.shape
    # Boş alan ve toplam araç sayısını ekrana yazdır
    cv2.putText(frame, f'Bos Alan: {empty_count}', (width-150,30 ), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    cv2.putText(frame, f'Toplam Arac: {occupied_count}', (width-150, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    
    
    # Alanların durumunu ekrana yazdır
    for i, area in enumerate(areas):
        area_key = area['block_name'] + ' - ' + str(area['area_number'])
        cursor.execute(
            "SELECT entry_time, exit_time FROM EntryExitRecords WHERE parking_area_id = %s ORDER BY entry_time DESC LIMIT 1",
            (area['id'],)
        )
        result = cursor.fetchone()
        if result:
            entry_time = result[0].strftime("%H:%M-%d/%m/%Y") if result[0] else None
            exit_time = result[1].strftime("%H:%M-%d/%m/%Y") if result[1] else None
            
            if exit_time:
                status_text = f'{area_key}: Bos Giris Saati: {entry_time} Cikis Saati: {exit_time}'
            else:
                status_text = f'{area_key}: Dolu Giris Saati: {entry_time} Cikis Saati: {exit_time}'
        else:
            status_text = f'{area_key}: Bos'

        cv2.putText(frame, status_text, (10, 30 + 20*i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        
    cv2.imshow('FRAME', frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
