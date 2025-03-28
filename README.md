# 🚗 Otopark Araç Tespit ve Takip Sistemi  

Bu proje, **YOLO (You Only Look Once) nesne algılama modeli ve OpenCV** kullanarak otoparktaki araçları tespit eden ve **PostgreSQL** veritabanı ile giriş-çıkış kayıtlarını tutan bir sistemdir.  

## 🚀 Özellikler  
✅ **Araç Tespiti:** YOLO modeli ile araçları algılar.  
✅ **Park Alanlarının Tanımlanması:** Kullanıcı fare ile park alanlarını belirleyebilir.  
✅ **Gerçek Zamanlı Kayıt:** Araçların giriş-çıkış saatleri PostgreSQL’e kaydedilir.  
✅ **Boş/Dolu Alan Analizi:** Park alanlarının doluluk durumu gösterilir.  
✅ **Görselleştirme:** Çerçeveler ve analiz sonuçları OpenCV ile ekranda gösterilir.  

---

## 🛠 Kullanılan Teknolojiler  
- **Python** - Ana programlama dili  
- **OpenCV** - Görüntü işleme ve araç tespiti  
- **YOLO (ultralytics)** - Nesne algılama modeli  
- **PostgreSQL** - Veritabanı yönetimi  
- **NumPy & Pandas** - Veri işleme ve analiz  
- **JSON** - Park alanı koordinatlarının saklanması  

---

## 📌 Kurulum ve Kullanım  

### 1️⃣ Gerekli Bağımlılıkları Kurun  
```bash
pip install ultralytics opencv-python numpy pandas psycopg2 json
