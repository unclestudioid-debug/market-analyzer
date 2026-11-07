# Market Analyzer — Aplikasi Web

Dashboard web untuk menganalisis BTC/USD, ETH/USD, XRP/USD, SOL/USD, XAUUSD, dan WTI dari berita serta indikator teknikal.

## Menjalankan di komputer (Mac / Windows)

1. Install Python 3.10 atau lebih baru.
2. Ekstrak ZIP ini.
3. Buka Terminal di folder `market_analyzer_app`.
4. Jalankan:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Di Windows, aktifkan virtual environment dengan `.venv\Scripts\activate`.
Browser akan membuka alamat lokal, biasanya `http://localhost:8501`.

## Online / bisa dibuka dari mana saja

Aplikasi ini memakai Python untuk mengambil RSS dan data harga, jadi bukan situs HTML statis biasa.
Cara termudah adalah deploy ke Streamlit Community Cloud:

1. Upload isi folder ini ke repository GitHub.
2. Masuk ke https://share.streamlit.io/
3. Hubungkan GitHub dan pilih repository.
4. Pilih file utama `app.py`, lalu deploy.

## Fitur

- Analisis terpisah untuk BTC, ETH, XRP, SOL, XAUUSD, dan WTI.
- Berita dari Google News RSS, CoinDesk, Cointelegraph, dan OilPrice.
- Data harga harian Yahoo Finance.
- RSI, EMA20/EMA50, MACD histogram, momentum 5 hari.
- Bobot berita dan teknikal dapat diubah.
- Filter berita berdasarkan aset.
- Ekspor hasil ke JSON dan judul berita ke TXT.

## Catatan

- Perlu koneksi internet saat aplikasi berjalan.
- Sumber data gratis dapat membatasi permintaan atau tidak selalu tersedia.
- Analisis berita menggunakan pencocokan kata kunci; bukan model pemahaman konteks.
- Skor bukan sinyal trading yang terjamin dan bukan saran investasi.


## Metode pembobotan

Bobot analisis ditetapkan tetap pada 70% skor berita dan 30% skor teknikal. Jika data teknikal tidak tersedia untuk suatu aset, aplikasi memberi peringatan dan skor sementara memakai berita saja.
