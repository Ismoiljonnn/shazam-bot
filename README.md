# 🎬 MediaBot — Telegram Video Yuklash Boti

## Nima qiladi?

- ✅ **Video yuklash**: YouTube, Instagram, TikTok, Twitter/X, Facebook, VK va 1000+ sayt
- ✅ **Audio yuklash**: Istalgan video dan MP3 format
- ✅ **Musiqa aniqlash**: Video/audio/yumaloq video yuborsangiz, Shazam orqali musiqani topadi
- ✅ **Admin panel**: Foydalanuvchilar, yuklamalar statistikasi, xabar yuborish

---

## 📁 Fayl tuzilmasi

```
mediabot/
├── app.py              # Asosiy Flask ilovasi + Admin panel
├── bot.py              # Telegram bot mantig'i
├── models.py           # Ma'lumotlar bazasi modellari
├── requirements.txt    # Python kutubxonalari
├── render.yaml         # Render.com konfiguratsiyasi
├── .env.example        # Muhit o'zgaruvchilari namunasi
└── templates/          # HTML shablonlar
    ├── base.html
    ├── login.html
    ├── layout.html
    ├── dashboard.html
    ├── users.html
    ├── user_detail.html
    ├── downloads.html
    ├── broadcast.html
    └── settings.html
```

---

## 🚀 Render.com da Deploy qilish — To'liq Yo'riqnoma

### 1-qadam: Telegram Bot Token olish

1. Telegramda **@BotFather** ga yozing
2. `/newbot` buyrug'ini yuboring
3. Bot nomini kiriting (masalan: `MyMediaBot`)
4. Bot username kiriting (masalan: `my_media_bot`)
5. **Token** ni nusxalang — shunday ko'rinadi: `7234567890:AAF-aBcDeFgHiJkLmNoPqRsTuVwXyZ`

### 2-qadam: GitHub ga yuklash

```bash
# Terminal/CMD da:
git init
git add .
git commit -m "Initial commit"

# GitHub da yangi repository yarating:
# github.com → New repository → mediabot → Create

git remote add origin https://github.com/SIZNING_USERNAME/mediabot.git
git branch -M main
git push -u origin main
```

### 3-qadam: Render.com da ro'yxatdan o'tish

1. [render.com](https://render.com) ga kiring
2. **GitHub** bilan ro'yxatdan o'ting
3. **New +** → **Web Service** tugmasini bosing

### 4-qadam: Service sozlash

**Connect Repository bo'limida:**
- GitHub repository ni tanlang: `mediabot`
- **Connect** bosing

**Configure bo'limida:**
```
Name:          mediabot
Region:        Frankfurt (EU Central) — yaqinroq
Branch:        main
Runtime:       Python 3
Build Command: pip install -r requirements.txt
Start Command: python app.py
```

**Instance Type:**
- **Free** (bepul, lekin uyqu rejimi bor) YOKI
- **Starter** ($7/oy, 24/7 ishlaydi) — bot uchun tavsiya etiladi

### 5-qadam: Environment Variables (Muhim!)

**Environment** bo'limiga o'ting va quyidagilarni qo'shing:

| Key | Value | Izoh |
|-----|-------|------|
| `BOT_TOKEN` | `7234567890:AAF-...` | BotFather dan olgan token |
| `SECRET_KEY` | `mysupersecret123abc` | Xavfsizlik uchun (ixtiyoriy belgilar) |
| `ADMIN_USERNAME` | `admin` | Admin login |
| `ADMIN_PASSWORD` | `strong_password_here` | Admin parol (kuchli parol qo'ying!) |
| `MAX_FILE_SIZE_MB` | `50` | Maksimal fayl hajmi |
| `DOWNLOAD_TIMEOUT` | `300` | Yuklash vaqt chegarasi |
| `PORT` | `10000` | Render port |

### 6-qadam: Deploy

**Create Web Service** tugmasini bosing.

Deploy jarayoni 3-5 daqiqa davom etadi. Tugagach URL ko'rsatiladi:
```
https://mediabot-xxxx.onrender.com
```

### 7-qadam: Tekshirish

1. **Bot**: Telegramda botingizga `/start` yuboring
2. **Admin Panel**: `https://mediabot-xxxx.onrender.com/admin`
   - Login: `.env` da belgilagan username
   - Parol: `.env` da belgilagan password

---

## 🔧 Mahalliy (Local) Ishga Tushirish

```bash
# 1. Muhit o'rnatish
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Kutubxonalar o'rnatish
pip install -r requirements.txt

# 3. .env fayl yaratish
cp .env.example .env
# .env faylini oching va BOT_TOKEN ni kiriting

# 4. FFmpeg o'rnatish (audio uchun zarur)
# Ubuntu/Debian:
sudo apt install ffmpeg
# macOS:
brew install ffmpeg
# Windows: https://ffmpeg.org/download.html

# 5. Ishga tushirish
python app.py
```

---

## ⚠️ Muhim Eslatmalar

### Free Plan cheklovlari (Render.com):
- Bot 15 daqiqa faolsizlikdan keyin "uyquga" ketadi
- Uyg'otish uchun 30-60 soniya kerak
- Agar 24/7 ishlashi kerak bo'lsa — **Starter plan** ($7/oy) oling

### FFmpeg muammosi:
Render.com da FFmpeg odatda o'rnatilmagan. Audio yuklash ishlamasa, `render.yaml` ga qo'shing:
```yaml
buildCommand: apt-get install -y ffmpeg && pip install -r requirements.txt
```

### Ma'lumotlar bazasi:
- SQLite ishlatilmoqda (faylda saqlanadi)
- Render.com da deploy qayta bo'lganda ma'lumotlar o'chirilishi mumkin
- Muhimroq loyihalar uchun **PostgreSQL** dan foydalaning

---

## 🎵 Musiqa Aniqlash

`shazamio` kutubxonasi orqali ishlaydi. Agar ishlamasa:
```bash
pip install shazamio --upgrade
```

---

## 📊 Admin Panel

| URL | Izoh |
|-----|------|
| `/admin` | Dashboard — umumiy statistika |
| `/admin/users` | Foydalanuvchilar ro'yxati |
| `/admin/downloads` | Yuklamalar tarixi |
| `/admin/broadcast` | Barcha foydalanuvchilarga xabar |
| `/admin/settings` | Bot sozlamalari |

---

## 🛠️ Qo'llab-quvvatlanadigan Platformalar

YouTube • Instagram • TikTok • Twitter/X • Facebook • VK • Pinterest • Reddit • Twitch • Dailymotion va 1000+ boshqa saytlar

---

## 📝 Litsenziya

Bu loyiha shaxsiy foydalanish uchun mo'ljallangan.
