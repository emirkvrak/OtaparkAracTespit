import cv2
import numpy as np
import psycopg2

# PostgreSQL veritabanına bağlanın
try:
    conn = psycopg2.connect(
        dbname="OtaparkVerileri",
        user="postgres",
        password="846203",
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor()

    # Blocks ve ParkingAreas tablolarını oluşturun (varsa geç)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Blocks (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ParkingAreas (
            id SERIAL PRIMARY KEY,
            block_id INTEGER REFERENCES Blocks(id),
            area_number INTEGER,
            is_full BOOLEAN DEFAULT FALSE,
            points TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS EntryExitRecords (
            id SERIAL PRIMARY KEY,
            parking_area_id INTEGER REFERENCES ParkingAreas(id),
            entry_time TIMESTAMP WITH TIME ZONE,
            exit_time TIMESTAMP WITH TIME ZONE
        )
    """)
    conn.commit()
except psycopg2.Error as e:
    print("Veritabanına bağlanırken bir hata oluştu:", e)
    exit()

areas = []
points = []  # Global olarak points değişkenini tanımla
frame = None  # Global olarak frame değişkenini tanımla

def delete_area(x, y):
    global areas
    for i, area in enumerate(areas):
        points = area['points']
        rect = cv2.boundingRect(np.array(points))
        x1, y1, w, h = rect
        x2, y2 = x1 + w, y1 + h
        if x1 <= x <= x2 and y1 <= y <= y2:
            cursor.execute(
                "DELETE FROM EntryExitRecords WHERE parking_area_id = %s",
                (area['id'],)
            )
            conn.commit()
            cursor.execute(
                "DELETE FROM ParkingAreas WHERE id = %s",
                (area['id'],)
            )
            conn.commit()
            del areas[i]
            break


def add_area():
    
    global points
    points_array = np.array(points, np.int32)
    while True:
        if len(points) != 4:  # Dikdörtgen oluşturmak için 4 nokta gereklidir
            print("Dikdörtgen tanımlamak için 4 noktaya ihtiyacınız var.")
            return
        block_name = input("Blok adını girin (yalnızca büyük harfler): ")
        area_number = input("Alan numarasını girin (pozitif tamsayı): ")

        # Aynı blok adı ve alan numarasıyla bir giriş var mı kontrol et
        cursor.execute(
            "SELECT COUNT(*) FROM ParkingAreas pa JOIN Blocks b ON pa.block_id = b.id WHERE b.name = %s AND pa.area_number = %s",
            (block_name, area_number)
        )
        count = cursor.fetchone()[0]
        if count > 0:
            print("Bu blok adı ve alan numarası zaten kullanılmış. Lütfen tekrar deneyin.")
            continue

        # Bloğu önceden kontrol et ve yoksa ekle
        cursor.execute(
            "INSERT INTO Blocks (name) VALUES (%s) ON CONFLICT DO NOTHING RETURNING id",
            (block_name,)
        )
        result = cursor.fetchone()
        if result is not None:
            block_id = result[0]
        else:
            # Blok zaten var, ID'sini al
            cursor.execute(
                "SELECT id FROM Blocks WHERE name = %s",
                (block_name,)
            )
            block_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO ParkingAreas (block_id, area_number, points) VALUES (%s, %s, %s) RETURNING id",
            (block_id, area_number, points_array.tolist())
        )
        area_id = cursor.fetchone()[0]

        areas.append({'id': area_id, 'points': points_array.tolist(), 'area_number': area_number, 'block_name': block_name})
        points = []  # Alan ekledikten sonra noktaları sıfırla
        break


def show_areas(frame):
    global areas
    areas = []  # Reset areas list
    # Fetch previously drawn areas from the database
    cursor.execute("SELECT pa.id, pa.points, pa.area_number, b.name FROM ParkingAreas pa JOIN Blocks b ON pa.block_id = b.id")
    records = cursor.fetchall()

    for record in records:
        points_str = record[1][1:-1].split('},{')  # Remove curly braces and split string
        points = []
        for p in points_str:
            if p.startswith('{'):
                p = p[1:]
            if p.endswith('}'):
                p = p[:-1]
            points.append(tuple(map(int, p.split(','))))
        block_name = record[3]
        area_number = record[2]
        areas.append({'id': record[0], 'points': points, 'area_number': area_number, 'block_name': block_name})
        cv2.polylines(frame, [np.array(points, np.int32)], True, (0, 255, 0), 2)  # Draw the polygon
        cv2.putText(frame, f"{block_name}-{area_number}", tuple(points[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)  # Display the text

    cv2.imshow('FRAME', frame)


def draw_area(event, x, y, flags, param):
    global points
    global frame  # frame global değişkenini kullanmak için
    if event == cv2.EVENT_LBUTTONDOWN:
        if len(points) < 4:
            points.append((x, y))
        if len(points) == 4:
            frame_copy = frame.copy()  # Çizim işleminin orijinal görüntüyü etkilememesi için kopyasını oluştur
            cv2.polylines(frame_copy, [np.array(points, np.int32)], True, (0, 255, 0), 2)  # Dikdörtgen çiz
            cv2.imshow('FRAME', frame_copy)  # Çizimleri ekranda göster
            add_area()
    elif event == cv2.EVENT_RBUTTONDOWN:
        delete_area(x, y)



cv2.namedWindow('FRAME', cv2.WINDOW_NORMAL)  # Pencereyi normal boyutta oluştur
cv2.setMouseCallback('FRAME', draw_area)

cap = cv2.VideoCapture('video.mp4')

while True:
    ret, frame = cap.read()
    if not ret:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue
    frame = cv2.resize(frame, ( 1800, 900))  # Her kareyi 1080x1080 boyutunda göster
    show_areas(frame)
    cv2.imshow('FRAME', frame)
    key = cv2.waitKey(1) & 0xFF  # waitKey değerini 1'e düşürdük
    if key == ord('q'):
        break
    if key == ord('s'):
        conn.commit()
    cv2.waitKey(1)  # Pencereyi güncellemek için bu satırı ekledik

# Cursor ve bağlantıyı kapatın
cursor.close()
conn.close()

cap.release()
cv2.destroyAllWindows()
