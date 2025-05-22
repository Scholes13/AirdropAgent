# AirdropAgent

AirdropAgent adalah sebuah AI agent yang mengevaluasi dan memberikan rating pada airdrop cryptocurrency dari Twitter.

## Fitur Utama

- 🤖 **AI Analysis**: Menggunakan model Gemini Pro via OpenRouter untuk analisis airdrop
- 🔍 **Twitter Scraper**: Mencari dan mengumpulkan tweet terbaru dengan hashtag #airdrop
- 🌐 **Website Scraper**: Mengumpulkan data tambahan dari website project untuk analisis lebih dalam
- 📊 **Dashboard Web**: Antarmuka web untuk melihat airdrop yang dianalisis
- ⚠️ **Deteksi Scam**: Mendeteksi red flags dan memberikan peringatan untuk kemungkinan scam
- 📈 **Rating System**: Rating 1-10 untuk setiap airdrop berdasarkan berbagai faktor

## Arsitektur

- **Backend**: Python dengan Flask
- **Web Scraping**: Selenium dan BeautifulSoup
- **Database**: SQLite
- **AI**: Integrasi dengan OpenRouter API (Gemini Pro)
- **Frontend**: HTML/CSS/JavaScript dengan Bootstrap

## Setup

### Prasyarat

- Python 3.8+
- Chrome browser (untuk Selenium)
- Chrome WebDriver

### Instalasi

1. Clone repository:
```
git clone <repository-url>
cd AirdropAgent
```

2. Install dependencies:
```
pip install -r requirements.txt
```

3. Konfigurasi kredensial:
   - Edit `config.py` dengan kredensial Twitter dan API key OpenRouter Anda

4. Jalankan aplikasi:
```
python main.py
```

## Penggunaan

1. Akses web interface di `http://localhost:5000`
2. Login dengan kredensial (default: admin/password123)
3. Lihat dashboard dengan airdrop terbaru dan statistik
4. Lihat detail analisis untuk setiap airdrop

## Komponen Utama

- `main.py`: Script utama untuk menjalankan aplikasi
- `app/scraper/twitter_bot.py`: Scraper Twitter
- `app/scraper/website_scraper.py`: Scraper website project
- `app/models/ai_analyzer.py`: Modul AI untuk menganalisis airdrop
- `web/app.py`: Aplikasi web Flask
- `database.py`: Modul database SQLite

## Penting

- Ganti password default di `config.py` sebelum deployment
- Twitter mungkin memblokir akses jika ada terlalu banyak request
- OpenRouter memiliki batasan API calls, sesuaikan `SEARCH_INTERVAL_MINUTES` untuk menghindari rate limiting 