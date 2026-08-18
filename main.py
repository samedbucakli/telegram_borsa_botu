import os
import time
import requests
import schedule
import feedparser
import yfinance as yf
import threading
from flask import Flask

# --- AYARLAR VE GİZLİ BİLGİLER ---
# Render.com'da Environment Variables kısmına bu bilgileri gireceğiz.
TOKEN = os.environ.get("TELEGRAM_TOKEN", "BURAYA_TOKEN_YAZIN_VEYA_ENV_KULLANIN")
CHAT_ID = os.environ.get("CHAT_ID", "BURAYA_KANAL_ID_YAZIN")

# Gönderilen haberleri tutacağımız küme (Aynı haberi 2 kez atmamak için)
gonderilen_haberler = set()

# Sadece bu kelimeleri içeren haberler "Önemli" sayılıp kanala atılacak
ONEMLI_KELIMELER = [
    "faiz", "enflasyon", "merkez bankası", "tcmb", "fed", "bist", "borsa", 
    "dolar", "altın", "kripto", "bitcoin", "vergi", "büyüme", "kapanış", "açılış",
    "kredi", "rezerv", "spk", "bddk"
]

# --- RENDER.COM İÇİN DUMMY WEB SUNUCUSU (Uyumaması için) ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot aktif ve çalışıyor!"

# --- TELEGRAM MESAJ GÖNDERİCİ ---
def telegrama_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mesaj,
        "parse_mode": "HTML",
        "disable_web_page_preview": False # Link önizlemesi açık olsun
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Mesaj gönderilemedi:", e)

# --- ANLIK HABER KONTROLÜ ---
def son_dakika_kontrol():
    # Bloomberg HT RSS Linki
    rss_url = "https://www.bloomberght.com/rss"
    try:
        feed = feedparser.parse(rss_url)
        
        for haber in feed.entries[:5]: # En son 5 haberi kontrol et
            haber_linki = haber.link
            haber_basligi = haber.title
            
            # 1. Haber daha önce gönderilmiş mi?
            if haber_linki not in gonderilen_haberler:
                # 2. Haber başlığı önemli kelimelerden birini içeriyor mu?
                baslik_kucuk = haber_basligi.lower()
                if any(kelime in baslik_kucuk for kelime in ONEMLI_KELIMELER):
                    
                    mesaj = f"🚨 <b>PİYASA HABERİ</b>\n\n🗞 {haber_basligi}\n\n🔗 <a href='{haber_linki}'>Haberi Oku</a>"
                    telegrama_gonder(mesaj)
                    
                    gonderilen_haberler.add(haber_linki)
                    
                else:
                    # Önemli değilse bile gönderildi say ki sürekli kontrol edip sistemi yormasın
                    gonderilen_haberler.add(haber_linki)
                    
        # Hafıza yönetimi: Set çok büyümesin
        if len(gonderilen_haberler) > 200:
            gonderilen_haberler.clear()
            
    except Exception as e:
        print("RSS çekilirken hata:", e)

# --- GÜNLÜK PİYASA ÖZETİ (Yahoo Finance ile) ---
def piyasa_ozeti_gonder():
    try:
        # Verileri çekiyoruz
        bist100 = yf.Ticker("XU100.IS").history(period="1d")
        dolar = yf.Ticker("TRY=X").history(period="1d")
        altin = yf.Ticker("GC=F").history(period="1d") # Ons altın (Gram için formül yazılabilir)
        
        # Kapanış fiyatlarını alıyoruz
        bist_fiyat = round(bist100['Close'].iloc[0], 2) if not bist100.empty else "Veri Yok"
        dolar_fiyat = round(dolar['Close'].iloc[0], 4) if not dolar.empty else "Veri Yok"
        altin_fiyat = round(altin['Close'].iloc[0], 2) if not altin.empty else "Veri Yok"

        mesaj = f"""
📊 <b>Günün Piyasa Kapanış Özeti</b>

🇹🇷 <b>BIST 100:</b> {bist_fiyat}
💵 <b>Dolar/TL:</b> {dolar_fiyat}
🥇 <b>Altın (Ons):</b> ${altin_fiyat}

<i>İyi akşamlar dileriz...</i>
"""
        telegrama_gonder(mesaj)
    except Exception as e:
        print("Piyasa özeti çekilirken hata:", e)

# --- BOT DÖNGÜSÜ (Arka Planda Çalışacak) ---
def bot_baslat():
    # Haberleri her 3 dakikada bir kontrol et
    schedule.every(3).minutes.do(son_dakika_kontrol)
    
    # Piyasa özetini hafta içi her gün 18:30'da gönder (Türkiye saati ile)
    schedule.every().monday.at("18:30").do(piyasa_ozeti_gonder)
    schedule.every().tuesday.at("18:30").do(piyasa_ozeti_gonder)
    schedule.every().wednesday.at("18:30").do(piyasa_ozeti_gonder)
    schedule.every().thursday.at("18:30").do(piyasa_ozeti_gonder)
    schedule.every().friday.at("18:30").do(piyasa_ozeti_gonder)

    print("Bot döngüsü başladı...")
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == '__main__':
    # Botu ayrı bir thread (iş parçacığı) olarak başlatıyoruz
    bot_thread = threading.Thread(target=bot_baslat)
    bot_thread.start()
    
    # Render.com'un web servisini başlatıyoruz (Uygulamanın ayakta kalması için şart)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)