#!/bin/bash
# Render.com uchun ishga tushirish skripti

echo "🚀 MediaBot ishga tushirilmoqda..."

# FFmpeg o'rnatish (audio konvertatsiya uchun)
apt-get install -y ffmpeg 2>/dev/null || true

# Ma'lumotlar bazasini boshlash
python -c "
from app import app, init_db
init_db()
print('✅ Database tayyor')
"

# Asosiy dasturni ishga tushirish
echo "✅ Server va bot ishga tushirilmoqda..."
python app.py
