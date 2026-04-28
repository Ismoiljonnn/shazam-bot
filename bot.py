import os
import asyncio
import logging
import tempfile
import re
from pathlib import Path
from datetime import datetime

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ParseMode, ChatAction

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE_MB', 50)) * 1024 * 1024


def detect_platform(url: str) -> str:
    url_lower = url.lower()
    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'YouTube'
    elif 'instagram.com' in url_lower:
        return 'Instagram'
    elif 'tiktok.com' in url_lower:
        return 'TikTok'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'Twitter/X'
    elif 'facebook.com' in url_lower or 'fb.com' in url_lower:
        return 'Facebook'
    elif 'vk.com' in url_lower:
        return 'VKontakte'
    elif 'pinterest.com' in url_lower:
        return 'Pinterest'
    elif 'reddit.com' in url_lower:
        return 'Reddit'
    elif 'twitch.tv' in url_lower:
        return 'Twitch'
    elif 'dailymotion.com' in url_lower:
        return 'Dailymotion'
    else:
        return 'Boshqa'


def is_valid_url(text: str) -> bool:
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return bool(url_pattern.search(text))


async def download_video(url: str, output_dir: str, audio_only: bool = False) -> dict:
    ydl_opts = {
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    if audio_only:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        ydl_opts.update({
            'format': 'best[filesize<50M]/bestvideo[filesize<50M]+bestaudio/best',
            'merge_output_format': 'mp4',
        })
    
    loop = asyncio.get_event_loop()
    
    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info
    
    info = await loop.run_in_executor(None, _download)
    
    files = list(Path(output_dir).glob('*'))
    if not files:
        raise Exception("Fayl yuklab olinmadi")
    
    file_path = str(max(files, key=lambda f: f.stat().st_size))
    file_size = os.path.getsize(file_path)
    
    return {
        'path': file_path,
        'title': info.get('title', 'Video'),
        'duration': info.get('duration', 0),
        'uploader': info.get('uploader', ''),
        'thumbnail': info.get('thumbnail', ''),
        'size': file_size,
        'ext': info.get('ext', 'mp4'),
    }


async def get_video_info(url: str) -> dict:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    loop = asyncio.get_event_loop()
    
    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    
    return await loop.run_in_executor(None, _extract)


# ======================== HANDLERS ========================

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # DB ga saqlash
    try:
        from app import app, db
        from models import User
        with app.app_context():
            db_user = User.query.filter_by(telegram_id=user.id).first()
            if not db_user:
                db_user = User(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
                db.session.add(db_user)
                db.session.commit()
            else:
                db_user.last_active = datetime.utcnow()
                db.session.commit()
    except Exception as e:
        logger.error(f"DB error: {e}")

    welcome_text = f"""
🎬 *Salom, {user.first_name}!* Xush kelibsiz!

🤖 Men — **MediaBot**. Sizga quyidagi xizmatlarni taqdim etaman:

📥 *Video yuklash:*
• YouTube, Instagram, TikTok
• Twitter/X, Facebook, VK
• Va boshqa 1000+ sayt

🎵 *Musiqa aniqlash:*
• Video/audio yuboring
• Yumaloq video (voice note) yuboring
• Men musiqani topib beraman!

📤 *Foydalanish:*
Shunchaki havola (link) yuboring!

━━━━━━━━━━━━━━━
/help — Yordam
/stats — Statistika
    """
    
    keyboard = [
        [InlineKeyboardButton("❓ Yordam", callback_data='help'),
         InlineKeyboardButton("📊 Statistika", callback_data='stats')],
        [InlineKeyboardButton("💬 Muallif", url='https://t.me/your_username')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text, 
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📖 *Yordam — MediaBot*

*Qo'llab-quvvatlanadigan platformalar:*
✅ YouTube (video + audio)
✅ Instagram (post, reel, story)
✅ TikTok (video)
✅ Twitter / X
✅ Facebook
✅ VKontakte
✅ Pinterest
✅ Reddit
✅ Twitch clips
✅ Dailymotion
✅ Va 1000+ boshqa saytlar

*Musiqa aniqlash:*
🎵 Video yuboring → musiqa topiladi
🎵 Audio fayl yuboring → musiqa topiladi  
🎵 Yumaloq video yuboring → musiqa topiladi

*Buyruqlar:*
/start — Botni ishga tushirish
/help — Yordam
/stats — Sizning statistikangiz
/cancel — Amalni bekor qilish

*Eslatma:*
⚠️ Fayllar max 50MB bo'lishi kerak
⏱️ Yuklab olish 1-3 daqiqa olishi mumkin
    """
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            help_text, parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    try:
        from app import app, db
        from models import User
        with app.app_context():
            db_user = User.query.filter_by(telegram_id=user.id).first()
            downloads = db_user.total_downloads if db_user else 0
            joined = db_user.joined_at.strftime('%d.%m.%Y') if db_user else 'Noma\'lum'
    except:
        downloads = 0
        joined = 'Noma\'lum'
    
    stats_text = f"""
📊 *Sizning statistikangiz:*

👤 Foydalanuvchi: {user.first_name}
🆔 ID: `{user.id}`
📅 Ro'yxatdan o'tgan: {joined}
📥 Jami yuklamalar: {downloads}

━━━━━━━━━━━━━━━
Bot haqida ma'lumot:
🌐 1000+ platforma qo'llab-quvvatlanadi
    """
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            stats_text, parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)


async def url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    
    # URL tekshirish
    if not is_valid_url(text):
        await update.message.reply_text(
            "❌ Noto'g'ri havola. Iltimos, to'g'ri URL yuboring.\n\n"
            "Masalan: `https://youtube.com/watch?v=...`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # User ban tekshirish
    try:
        from app import app, db
        from models import User, Download
        with app.app_context():
            db_user = User.query.filter_by(telegram_id=user.id).first()
            if db_user and db_user.is_banned:
                await update.message.reply_text("🚫 Siz botdan foydalana olmaysiz.")
                return
    except:
        pass
    
    platform = detect_platform(text)
    
    # Format tanlash klaviaturasi
    keyboard = [
        [InlineKeyboardButton("🎬 Video (MP4)", callback_data=f'dl_video|{text}'),
         InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f'dl_audio|{text}')],
        [InlineKeyboardButton("ℹ️ Ma'lumot olish", callback_data=f'dl_info|{text}')],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🔗 *Havola aniqlandi!*\n\n"
        f"📱 Platforma: **{platform}**\n"
        f"🔗 URL: `{text[:50]}...`\n\n"
        f"Qaysi formatda yuklamoqchisiz?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    
    if data == 'help':
        await help_handler(update, context)
        return
    
    if data == 'stats':
        await stats_handler(update, context)
        return
    
    if data == 'cancel':
        await query.edit_message_text("❌ Bekor qilindi.")
        return
    
    if data.startswith('dl_info|'):
        url = data.split('|', 1)[1]
        await query.edit_message_text("⏳ Ma'lumot olinmoqda...")
        
        try:
            info = await get_video_info(url)
            duration = info.get('duration', 0)
            mins = duration // 60
            secs = duration % 60
            
            info_text = (
                f"📋 *Video ma'lumoti:*\n\n"
                f"🎬 Sarlavha: {info.get('title', 'Noma\'lum')[:100]}\n"
                f"👤 Muallif: {info.get('uploader', 'Noma\'lum')}\n"
                f"⏱️ Davomiyligi: {mins}:{secs:02d}\n"
                f"👁️ Ko'rishlar: {info.get('view_count', 0):,}\n"
                f"❤️ Yoqtirishlar: {info.get('like_count', 0):,}\n"
            )
            
            keyboard = [
                [InlineKeyboardButton("🎬 Video yuklab olish", callback_data=f'dl_video|{url}'),
                 InlineKeyboardButton("🎵 Audio yuklab olish", callback_data=f'dl_audio|{url}')],
                [InlineKeyboardButton("❌ Yopish", callback_data='cancel')]
            ]
            await query.edit_message_text(
                info_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Ma'lumot olishda xato: {str(e)[:100]}")
        return
    
    if data.startswith('dl_video|') or data.startswith('dl_audio|'):
        is_audio = data.startswith('dl_audio|')
        url = data.split('|', 1)[1]
        platform = detect_platform(url)
        
        await query.edit_message_text(
            f"⏳ *Yuklab olinmoqda...*\n\n"
            f"📱 Platforma: {platform}\n"
            f"📁 Format: {'🎵 Audio (MP3)' if is_audio else '🎬 Video (MP4)'}\n\n"
            f"_Iltimos, kuting..._",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await context.bot.send_chat_action(
            chat_id=query.message.chat_id,
            action=ChatAction.UPLOAD_VIDEO if not is_audio else ChatAction.UPLOAD_VOICE
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                result = await download_video(url, tmpdir, audio_only=is_audio)
                
                file_path = result['path']
                title = result['title']
                
                if os.path.getsize(file_path) > MAX_FILE_SIZE:
                    await query.edit_message_text(
                        "❌ Fayl juda katta (50MB dan oshdi).\n"
                        "Iltimos, qisqaroq video tanlang."
                    )
                    return
                
                caption = (
                    f"✅ *{title[:200]}*\n\n"
                    f"📱 {platform} | "
                    f"{'🎵 Audio' if is_audio else '🎬 Video'} | "
                    f"📦 {os.path.getsize(file_path) / 1024 / 1024:.1f}MB\n\n"
                    f"🤖 @{context.bot.username}"
                )
                
                with open(file_path, 'rb') as f:
                    if is_audio:
                        await context.bot.send_audio(
                            chat_id=query.message.chat_id,
                            audio=f,
                            caption=caption,
                            parse_mode=ParseMode.MARKDOWN,
                            title=title[:64],
                        )
                    else:
                        await context.bot.send_video(
                            chat_id=query.message.chat_id,
                            video=f,
                            caption=caption,
                            parse_mode=ParseMode.MARKDOWN,
                            supports_streaming=True,
                        )
                
                # DB yangilash
                try:
                    from app import app, db
                    from models import User, Download
                    with app.app_context():
                        db_user = User.query.filter_by(telegram_id=user.id).first()
                        if db_user:
                            db_user.total_downloads += 1
                            db_user.last_active = datetime.utcnow()
                        
                        dl = Download(
                            user_id=db_user.id if db_user else 1,
                            url=url,
                            platform=platform,
                            title=title[:500],
                            file_type='audio' if is_audio else 'video',
                            status='success'
                        )
                        db.session.add(dl)
                        db.session.commit()
                except Exception as e:
                    logger.error(f"DB error: {e}")
                
                await query.edit_message_text("✅ Fayl muvaffaqiyatli yuborildi!")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Download error: {error_msg}")
                
                user_msg = "❌ *Yuklab olishda xato:*\n\n"
                if 'Private' in error_msg or 'private' in error_msg:
                    user_msg += "🔒 Bu video yopiq (private). Ochiq videolarni yuboring."
                elif 'not available' in error_msg.lower():
                    user_msg += "🚫 Video mavjud emas yoki o'chirilgan."
                elif 'age' in error_msg.lower():
                    user_msg += "🔞 Bu video yosh cheklovi bilan himoyalangan."
                elif 'copyright' in error_msg.lower():
                    user_msg += "©️ Bu video mualliflik huquqi bilan himoyalangan."
                else:
                    user_msg += f"`{error_msg[:200]}`"
                
                await query.edit_message_text(user_msg, parse_mode=ParseMode.MARKDOWN)
                
                # DB ga yozish
                try:
                    from app import app, db
                    from models import User, Download
                    with app.app_context():
                        db_user = User.query.filter_by(telegram_id=user.id).first()
                        dl = Download(
                            user_id=db_user.id if db_user else 1,
                            url=url,
                            platform=platform,
                            file_type='audio' if is_audio else 'video',
                            status='failed',
                            error_msg=error_msg[:999]
                        )
                        db.session.add(dl)
                        db.session.commit()
                except:
                    pass


async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Video, audio yoki yumaloq video qabul qilganda musiqa aniqlash"""
    user = update.effective_user
    message = update.message
    
    # Qaysi turdagi media ekanlini aniqlash
    if message.video:
        media = message.video
        media_type = "video"
    elif message.audio:
        media = message.audio
        media_type = "audio"
    elif message.video_note:
        media = message.video_note
        media_type = "video_note"
    elif message.voice:
        media = message.voice
        media_type = "voice"
    else:
        return
    
    status_msg = await message.reply_text(
        "🎵 *Musiqa aniqlanmoqda...*\n\n"
        "⏳ Audio tahlil qilinmoqda, biroz kuting...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Faylni yuklash
            file = await context.bot.get_file(media.file_id)
            file_path = os.path.join(tmpdir, f"audio.{media.file_unique_id}")
            await file.download_to_drive(file_path)
            
# Faylni yuklash
            file = await context.bot.get_file(media.file_id)
            file_path = os.path.join(tmpdir, f"audio.{media.file_unique_id}")
            await file.download_to_drive(file_path)
            
            # AudD API orqali musiqa aniqlash (bepul, shazamio talab qilmaydi)
            try:
                import base64
                
                with open(file_path, 'rb') as f:
                    audio_data = base64.b64encode(f.read()).decode('utf-8')
                
                async with aiohttp.ClientSession() as session_http:
                    # AudD bepul API (ro'yxatdan o'tmasdan ishlaydi, lekin cheklangan)
                    form_data = aiohttp.FormData()
                    form_data.add_field('audio', audio_data)
                    form_data.add_field('return', 'apple_music,spotify')
                    
                    async with session_http.post(
                        'https://api.audd.io/',
                        data=form_data,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        result = await resp.json()
                
                if result.get('status') == 'success' and result.get('result'):
                    track = result['result']
                    song_title = track.get('title', 'Noma\'lum')
                    artist = track.get('artist', 'Noma\'lum')
                    album = track.get('album', '')
                    release_date = track.get('release_date', '')
                    
                    result_text = (
                        f"🎵 *Musiqa topildi!*\n\n"
                        f"🎶 Nomi: **{song_title}**\n"
                        f"👨‍🎤 Artist: **{artist}**\n"
                    )
                    if album:
                        result_text += f"💿 Albom: {album}\n"
                    if release_date:
                        result_text += f"📅 Sana: {release_date[:4]}\n"
                    
                    yt_search = f"https://www.youtube.com/results?search_query={song_title}+{artist}".replace(' ', '+')
                    spotify_search = f"https://open.spotify.com/search/{song_title} {artist}".replace(' ', '%20')
                    
                    # Spotify havolasi
                    spotify_url = ''
                    if track.get('spotify'):
                        spotify_url = track['spotify'].get('external_urls', {}).get('spotify', '')
                    
                    keyboard = [
                        [InlineKeyboardButton("🔴 YouTube", url=yt_search),
                         InlineKeyboardButton("🟢 Spotify", url=spotify_url or spotify_search)],
                    ]
                    
                    # Apple Music
                    if track.get('apple_music'):
                        apple_url = track['apple_music'].get('url', '')
                        if apple_url:
                            keyboard.append([InlineKeyboardButton("🍎 Apple Music", url=apple_url)])
                    
                    await status_msg.edit_text(
                        result_text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await status_msg.edit_text(
                        "❌ *Musiqa topilmadi.*\n\n"
                        "Bu video/audioda aniq musiqa ovozi bo'lmasligi mumkin.\n"
                        "Yoki ovoz sifati past bo'lishi mumkin.",
                        parse_mode=ParseMode.MARKDOWN
                    )
            except Exception as music_err:
                logger.error(f"Music detect error: {music_err}")
                await status_msg.edit_text(
                    "❌ *Musiqa aniqlashda xato yuz berdi.*\n\n"
                    "Iltimos qayta urinib ko'ring.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
        except Exception as e:
            logger.error(f"Music detection error: {e}")
            await status_msg.edit_text(
                f"❌ Xato yuz berdi: {str(e)[:200]}",
                parse_mode=ParseMode.MARKDOWN
            )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")


def create_bot_app():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, url_handler))
    app.add_handler(MessageHandler(
        filters.VIDEO | filters.AUDIO | filters.VIDEO_NOTE | filters.VOICE,
        media_handler
    ))
    app.add_error_handler(error_handler)
    
    return app


if __name__ == '__main__':
    bot_app = create_bot_app()
    bot_app.run_polling(drop_pending_updates=True)