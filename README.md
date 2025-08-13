OTOPARK ARAÇ TESPİT SİSTEMİ

Amaç:
YOLOv8 ve OpenCV kullanarak otopark alanlarındaki araçların tespiti ve doluluk/boşluk durumlarının PostgreSQL veritabanına kaydedilmesi.

![Proje Görseli](https://github.com/emirkvrak/OtaparkAracTespit/blob/main/images/carimage.png)

Kullanılan Teknolojiler:

- Python 3.10+
- OpenCV (cv2)
- NumPy
- Pandas
- Ultralytics YOLOv8
- PostgreSQL (psycopg2)
- python-dotenv

Kurulum:

1. Depoyu klonla:
   git clone https://github.com/emirkvrak/OtaparkAracTespit.git
   cd OtaparkAracTespit

2. Sanal ortam oluştur:
   python -m venv venv

3. Sanal ortamı aktif et:
   Windows PowerShell:
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\venv\Scripts\Activate

4. Gerekli kütüphaneleri yükle:
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt

Çalıştırma:

1. Alan çizimi yapmak için:
   python AlanCizimi2.py

   - Sol tık: Nokta ekler
   - Sağ tık: Alan siler
   - S: Kaydeder
   - Q: Çıkış

2. Araç tespiti yapmak için:
   python AraçSayimi.py

Not:

- PostgreSQL bilgilerini .env dosyasında ayarlayın.
- Model dosyası (yolov8s.pt) ilk çalıştırmada otomatik iner.
