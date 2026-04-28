#!/usr/bin/env python3
# coding: utf-8

import os
import re
import uuid
import glob
import json
import asyncio
import logging
import sqlite3
import shutil
import subprocess
from datetime import datetime
from typing import Optional, List

import aiosqlite
import yt_dlp
from shazamio import Shazam

from aiogram import Bot, Dispatcher
from aiogram.types import Message, ChatActions, ContentType, InputFile
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

from aiohttp import web

# Small server
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080)))
    await site.start()

async def main():
    await init_db()
    await start_web_server()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

# ---------- CONFIG ----------
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DB_PATH = "bot_users.db"
DOWNLOAD_DIR = "tmp_downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# create download dir
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- BOT & DISPATCHER ----------
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher()

# pending broadcast state for admin (in-memory)
pending_broadcast = set()  # user ids of admins expecting a broadcast message

# ---------- DATABASE HELPERS ----------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                join_date TEXT,
                banned INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def add_user(user_id: int, username: Optional[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, join_date) VALUES (?, ?, ?)",
            (user_id, username or "", now)
        )
        await db.commit()

async def get_user_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        row = await cur.fetchone()
        return row[0] if row else 0

async def get_all_users() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE banned = 0")
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if row:
            return bool(row[0])
        return False

# ---------- UTIL ----------
def make_temp_path(ext: str) -> str:
    name = f"{uuid.uuid4().hex}"
    return os.path.join(DOWNLOAD_DIR, f"{name}.{ext}")

def find_downloaded_file(prefix: str) -> Optional[str]:
    matches = glob.glob(os.path.join(DOWNLOAD_DIR, f"{prefix}.*"))
    return matches[0] if matches else None

async def run_subprocess(cmd: List[str]):
    # Run blocking subprocess in threadpool
    proc = await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc

# ---------- LINK DETECTION ----------
YTDLP_PATTERNS = {
    "youtube": re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/[^\s]+"),
    "tiktok": re.compile(r"(https?://)?(www\.)?tiktok\.com/[^\s]+"),
    "instagram": re.compile(r"(https?://)?(www\.)?instagram\.com/[^\s]+"),
}

def detect_supported_link(text: str) -> Optional[str]:
    if not text:
        return None
    for _, pattern in YTDLP_PATTERNS.items():
        m = pattern.search(text)
        if m:
            # return whole URL substring
            return m.group(0)
    # also try to extract URL via generic regex if above fails
    generic = re.search(r"https?://[^\s]+", text)
    return generic.group(0) if generic else None

# ---------- YT-DLP DOWNLOADER ----------
async def ytdlp_download(url: str) -> dict:
    """
    Returns dict with keys: filepath, filesize, ext, info
    Raises Exception on failure
    """
    # create unique prefix
    prefix = uuid.uuid4().hex
    outtmpl = os.path.join(DOWNLOAD_DIR, f"{prefix}.%(ext)s")
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        # avoid console encoding errors
        "ignoreerrors": False,
    }

    def run_ydl():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info

    try:
        info = await asyncio.to_thread(run_ydl)
    except Exception as e:
        logger.exception("yt-dlp failed")
        raise RuntimeError("Yuklashda xatolik: yt-dlp bajarilmadi.") from e

    # find real downloaded file
    filepath = find_downloaded_file(prefix)
    if not filepath:
        raise RuntimeError("Yuklangan fayl topilmadi.")
    filesize = os.path.getsize(filepath)
    ext = filepath.split(".")[-1]
    return {"filepath": filepath, "filesize": filesize, "ext": ext, "info": info}

# ---------- AUDIO EXTRACTION (ffmpeg) ----------
async def extract_audio(input_path: str, out_ext: str = "mp3") -> str:
    """
    Uses ffmpeg to extract audio to mp3 (or other out_ext).
    Returns path to audio file.
    """
    out_path = os.path.splitext(input_path)[0] + f".{out_ext}"
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", input_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-ar", "44100",
        "-ac", "2",
        out_path,
    ]
    proc = await run_subprocess(cmd)
    if proc.returncode != 0:
        logger.error("ffmpeg stderr: %s", proc.stderr.decode(errors="ignore") if proc.stderr else "")
        raise RuntimeError("Audio ajratishda xatolik yuz berdi.")
    if not os.path.exists(out_path):
        raise RuntimeError("Audio fayl topilmadi.")
    return out_path

# ---------- SHAZAM RECOGNITION ----------
shazam = Shazam()

async def recognize_song(audio_path: str) -> Optional[dict]:
    """
    Returns dict with 'title' and 'artist' or None if not found
    """
    try:
        # shazamio supports async file recognition
        out = await shazam.recognize_song(audio_path)
        # structure may vary; try to parse common fields
        track = out.get("track") if isinstance(out, dict) else None
        if track:
            title = track.get("title") or track.get("subtitle")
            artist = track.get("subtitle") or ""
            return {"title": title, "artist": artist, "raw": out}
        # alternative structure
        matches = out.get("matches") if isinstance(out, dict) else None
        if matches:
            # fallback: return raw
            return {"title": json.dumps(out)[:200], "artist": "", "raw": out}
    except Exception as e:
        logger.exception("Shazam recognition failed")
        return None
    return None

# ---------- HANDLERS ----------
async def check_and_register_user(message: Message):
    uid = message.from_user.id
    uname = message.from_user.username
    await add_user(uid, uname)

async def check_banned_and_notify(user_id: int) -> bool:
    if await is_banned(user_id):
        try:
            await bot.send_message(user_id, "Siz bloklangansiz. Botdan foydalanishningiz cheklangan.")
        except Exception:
            pass
        return True
    return False

@dp.message(Command("start"))
async def cmd_start(message: Message):
    if await check_banned_and_notify(message.from_user.id):
        return
    await check_and_register_user(message)
    await message.answer(
        "Assalomu alaykum! Men media yuklovchi va musiqa tanib olish botiman.\n"
        "URL yuborsangiz (YouTube, TikTok, Instagram) men video yuklab beraman.\n"
        "Video/Voice yuboring, men Shazam orqali qo‘shiqni aniqlab beraman."
    )

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    total = await get_user_count()
    await message.answer(f"Foydalanuvchilar soni: {total}")

@dp.message(Command("ban"))
async def cmd_ban(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    # Expecting: /ban <user_id>
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("Iltimos: /ban <user_id> formatida yuboring.")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("Foydalanuvchi ID noto‘g‘ri.")
        return
    await ban_user(uid)
    await message.answer(f"{uid} IDli foydalanuvchi bloklandi.")

@dp.message(Command("send_ad"))
async def cmd_send_ad(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    # mark admin as pending broadcast sender
    pending_broadcast.add(message.from_user.id)
    await message.answer("Reklama yuborishni boshlash uchun xabar yuboring (text, photo yoki video).")

@dp.message()
async def handle_broadcast_or_link_or_media(message: Message):
    """
    This handler manages:
    - if admin is pending broadcast, treat incoming message as broadcast content
    - link detection for downloading
    - media messages for Shazam recognition
    """
    if message.from_user is None:
        return

    uid = message.from_user.id

    # Register user on any interaction
    await check_and_register_user(message)

    # If admin pending broadcast
    if uid in pending_broadcast and uid == ADMIN_ID:
        pending_broadcast.remove(uid)
        await message.answer("Reklama yuborish boshlandi. Iltimos kuting...")
        # prepare list of recipients
        recipients = await get_all_users()
        text_preview = " (matn)" if message.text else ""
        # broadcast
        sent = 0
        failed = 0
        for r in recipients:
            try:
                if message.text:
                    await bot.send_message(r, message.text)
                elif message.photo:
                    # send highest resolution photo
                    photo = message.photo[-1]
                    file = await photo.download()
                    await bot.send_chat_action(r, ChatActions.UPLOAD_PHOTO)
                    await bot.send_photo(r, photo=InputFile(file.name), caption=message.caption or "")
                    try:
                        os.remove(file.name)
                    except Exception:
                        pass
                elif message.video:
                    file = await message.video.download()
                    await bot.send_chat_action(r, ChatActions.UPLOAD_VIDEO)
                    await bot.send_video(r, video=InputFile(file.name), caption=message.caption or "")
                    try:
                        os.remove(file.name)
                    except Exception:
                        pass
                else:
                    # unsupported content types can be forwarded
                    await bot.forward_message(r, uid, message.message_id)
                sent += 1
                # small delay to avoid hitting rate limits
                await asyncio.sleep(0.05)
            except TelegramRetryAfter as e:
                # if flood wait suggested, sleep
                wait = int(e.retry_after) + 1
                logger.info("Sleeping due to retry after: %s", wait)
                await asyncio.sleep(wait)
                failed += 1
            except Exception as e:
                logger.exception("Broadcast failed for %s", r)
                failed += 1
        await message.answer(f"Yuborildi: {sent}, muvaffaqiyatsiz: {failed}")
        return

    # Check bans
    if await is_banned(uid):
        await message.answer("Siz bloklangansiz. Botdan foydalanish cheklangan.")
        return

    # If message contains supported link => try to download
    if message.text:
        link = detect_supported_link(message.text)
        if link:
            await handle_download_request(message, link)
            return

    # If message contains media for Shazam: video, voice, video_note
    if message.video or message.voice or message.video_note or message.audio:
        await handle_shazam_recognition(message)
        return

    # else, ignore or respond default
    await message.answer("Link (YouTube, TikTok, Instagram) yoki media yuboring (video/voice) — men yordam beraman.")

# ---------- DOWNLOAD HANDLER ----------
async def handle_download_request(message: Message, url: str):
    chat_id = message.chat.id
    await bot.send_chat_action(chat_id, ChatActions.TYPING)
    sent_msg = await message.answer("Yuklanmoqda... Iltimos kuting.")
    try:
        # show uploading action
        await bot.send_chat_action(chat_id, ChatActions.UPLOAD_VIDEO)
        # download via yt-dlp (in thread)
        result = await ytdlp_download(url)
    except Exception as e:
        logger.exception("Download failed")
        await sent_msg.edit_text("Yuklashda xatolik yuz berdi: " + str(e))
        return

    filepath = result["filepath"]
    filesize = result["filesize"]

    try:
        # size check
        if filesize > MAX_FILE_SIZE:
            await sent_msg.edit_text("Fayl hajmi 50MB dan katta. Bot orqali yuborib bo‘lmaydi.")
            return
        # send file
        await sent_msg.edit_text("Fayl yuklandi. Yuborilmoqda...")
        await bot.send_chat_action(chat_id, ChatActions.UPLOAD_VIDEO)
        with open(filepath, "rb") as f:
            await bot.send_video(chat_id, f, caption="Siz so‘ragan video")
        await sent_msg.delete()
    except TelegramBadRequest as e:
        logger.exception("Telegram error while sending")
        await sent_msg.edit_text("Faylni yuborishda xatolik: " + str(e))
    except Exception as e:
        logger.exception("Unexpected error while sending")
        await sent_msg.edit_text("Faylni yuborishda xatolik yuz berdi.")
    finally:
        # always remove the file
        try:
            os.remove(filepath)
        except Exception:
            pass

# ---------- SHAZAM HANDLER ----------
async def handle_shazam_recognition(message: Message):
    chat_id = message.chat.id
    tmp_in = None
    audio_file = None
    status_msg = await message.answer("Audio ajratilmoqda va tekshirilmoqda... Iltimos kuting.")
    try:
        # download incoming media to temp
        if message.voice:
            tmp_in = make_temp_path("oga")
            file = await message.voice.download(destination_file=tmp_in)
            input_path = tmp_in
        elif message.audio:
            tmp_in = make_temp_path("ogg")
            file = await message.audio.download(destination_file=tmp_in)
            input_path = tmp_in
        elif message.video or message.video_note:
            tmp_in = make_temp_path("mp4")
            # if video_note, it's small circular video
            file = await (message.video or message.video_note).download(destination_file=tmp_in)
            input_path = tmp_in
        else:
            await status_msg.edit_text("Media topilmadi.")
            return

        await bot.send_chat_action(chat_id, ChatActions.TYPING)

        # extract audio
        audio_file = await extract_audio(input_path, out_ext="mp3")

        # run shazam
        res = await recognize_song(audio_file)
        if not res:
            await status_msg.edit_text("Qo‘shiq topilmadi yoki aniqlash imkoni bo‘lmadi.")
            return

        title = res.get("title") or "Noma'lum"
        artist = res.get("artist") or ""
        reply = f"Topildi:\n<b>{title}</b>\nIjrochi: <i>{artist}</i>"
        await status_msg.edit_text(reply)
    except Exception as e:
        logger.exception("Shazam handler error")
        await status_msg.edit_text("Aniqlashda xatolik yuz berdi: " + str(e))
    finally:
        # cleanup
        for p in (tmp_in, audio_file):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

# ---------- STARTUP / SHUTDOWN ----------
async def on_startup():
    logger.info("Bot starting...")
    await init_db()

async def on_shutdown():
    logger.info("Bot shutting down...")
    try:
        await bot.session.close()
    except Exception:
        pass
    # cleanup tmp dir (safety)
    try:
        shutil.rmtree(DOWNLOAD_DIR)
    except Exception:
        pass

if __name__ == "__main__":
    try:
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        dp.run_polling(bot)
    except KeyboardInterrupt:
        logger.info("Stopped by user")