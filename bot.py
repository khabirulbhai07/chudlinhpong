import os
import logging
import requests
import json
import time
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from flask import Flask
from threading import Thread

# ==================== Logging Setup ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ==================== Config ====================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ZYLA_API_KEY = os.environ.get("ZYLA_API_KEY", "12368|FQZM8X1GtUdl98NngHB9tcM2Ff5caNkaoyiXAF7E")
PORT = int(os.environ.get("PORT", 10000))
BOT_USERNAME = "@NewSocialDLBot"

ZYLA_API_URL = "https://zylalabs.com/api/4146/facebook+download+api/7134/downloader"

# Telegram limits
TELEGRAM_UPLOAD_LIMIT = 2000 * 1024 * 1024  # 2GB for local upload via file
TELEGRAM_DIRECT_LIMIT = 50 * 1024 * 1024     # 50MB for URL method

# ==================== Flask Keep-Alive ====================
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot is alive!", 200

@app_flask.route("/health")
def health():
    return "OK", 200

def run_flask():
    app_flask.run(host="0.0.0.0", port=PORT)

# ==================== Helper Functions ====================

def is_facebook_url(url: str) -> bool:
    fb_domains = [
        "facebook.com", "fb.com", "fb.watch",
        "www.facebook.com", "m.facebook.com", "web.facebook.com",
    ]
    return any(domain in url.lower() for domain in fb_domains)


def fetch_video_data(fb_url: str) -> dict:
    headers = {
        "Authorization": f"Bearer {ZYLA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = json.dumps({"url": fb_url})
    try:
        response = requests.post(ZYLA_API_URL, headers=headers, data=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API Error: {e}")
        return None


def format_duration(ms: int) -> str:
    if not ms:
        return "N/A"
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def get_quality_icon(quality: str) -> str:
    icons = {"HD": "🔵", "SD": "🟢", "Audio": "🟣"}
    return icons.get(quality, "⚪")


def get_file_size(url: str) -> int:
    """URL থেকে ফাইল সাইজ বের করে (bytes)"""
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        size = int(response.headers.get("content-length", 0))
        return size
    except Exception:
        return 0


def format_file_size(size_bytes: int) -> str:
    """Bytes কে readable format এ কনভার্ট করে"""
    if size_bytes <= 0:
        return "Unknown"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def download_file_to_temp(url: str, extension: str = "mp4") -> str:
    """ফাইল ডাউনলোড করে temporary path এ সেভ করে"""
    try:
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()

        temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{extension}", dir=tempfile.gettempdir()
        )
        
        downloaded = 0
        for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
            if chunk:
                temp_file.write(chunk)
                downloaded += len(chunk)
        
        temp_file.close()
        logger.info(f"Downloaded {format_file_size(downloaded)} to {temp_file.name}")
        return temp_file.name
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None


def cleanup_file(file_path: str):
    """Temporary ফাইল ডিলিট করে"""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up: {file_path}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


# ==================== Bot Commands Setup ====================

async def set_bot_commands(application):
    commands = [
        BotCommand("start", "🚀 Start the bot"),
        BotCommand("help", "📖 How to use this bot"),
        BotCommand("about", "ℹ️ About this bot"),
        BotCommand("supported", "📋 Supported link types"),
        BotCommand("stats", "📊 Your usage stats"),
        BotCommand("ping", "🏓 Check bot status"),
    ]
    await application.bot.set_my_commands(commands)


# ==================== Command Handlers ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name or "User"

    if "downloads" not in context.user_data:
        context.user_data["downloads"] = 0
        context.user_data["joined"] = time.strftime("%Y-%m-%d")

    welcome_text = (
        f"Hey **{first_name}**! 👋\n\n"
        f"Welcome to **Facebook Video Downloader** 🎬\n\n"
        f"I can download videos, reels & audio from Facebook — "
        f"**any size, any quality!** 🚀\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔹 Send me any Facebook video link\n"
        f"🔹 Choose your preferred quality\n"
        f"🔹 Get your video instantly!\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✨ **No size limit** — even 100MB+ videos!\n\n"
        f"💡 Type /help for detailed instructions.\n\n"
        f"⚡ Powered by {BOT_USERNAME}"
    )

    keyboard = [
        [
            InlineKeyboardButton("📖 How to Use", callback_data="cb_help"),
            InlineKeyboardButton("📋 Supported Links", callback_data="cb_supported"),
        ],
        [
            InlineKeyboardButton("ℹ️ About", callback_data="cb_about"),
            InlineKeyboardButton("🏓 Ping", callback_data="cb_ping"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        welcome_text, parse_mode="Markdown", reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **How to Use**\n\n"
        "Downloading a Facebook video is super easy:\n\n"
        "**Step 1️⃣** — Open Facebook & find the video\n"
        "**Step 2️⃣** — Tap `Share` → `Copy Link`\n"
        "**Step 3️⃣** — Paste the link here in chat\n"
        "**Step 4️⃣** — Select quality (HD / SD / Audio)\n"
        "**Step 5️⃣** — Done! Your file will be sent 🎉\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 **Commands:**\n"
        "/start — 🚀 Start the bot\n"
        "/help — 📖 How to use\n"
        "/about — ℹ️ About this bot\n"
        "/supported — 📋 Supported link types\n"
        "/stats — 📊 Your download stats\n"
        "/ping — 🏓 Check if bot is alive\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "✨ **New:** No file size limit! Large videos are\n"
        "downloaded to server first, then sent to you.\n\n"
        "⚠️ **Note:** Only public videos can be downloaded.\n\n"
        f"⚡ {BOT_USERNAME}"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    about_text = (
        "ℹ️ **About This Bot**\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 **Bot:** {BOT_USERNAME}\n"
        "📌 **Version:** 3.0\n"
        "🔧 **Language:** Python\n"
        "🌐 **API:** ZylaLabs\n"
        "☁️ **Hosted on:** Render\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 **Features:**\n"
        "├ 📹 Download FB Videos (Any Size!)\n"
        "├ 🎞️ Download FB Reels\n"
        "├ 🔵 HD Quality Support\n"
        "├ 🟢 SD Quality Support\n"
        "├ 🎵 Audio Extraction\n"
        "├ 🖼️ Thumbnail Preview\n"
        "├ 📦 File Size Detection\n"
        "├ ⚡ Fast & Reliable\n"
        "├ 🚫 No Size Limit\n"
        "└ 🆓 Completely Free\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Made with ❤️ by the developer.\n"
        f"⚡ {BOT_USERNAME}"
    )
    await update.message.reply_text(about_text, parse_mode="Markdown")


async def supported_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    supported_text = (
        "📋 **Supported Link Types**\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ **Supported:**\n"
        "├ 🔗 `facebook.com/watch/...`\n"
        "├ 🔗 `facebook.com/reel/...`\n"
        "├ 🔗 `facebook.com/video/...`\n"
        "├ 🔗 `facebook.com/share/v/...`\n"
        "├ 🔗 `fb.watch/...`\n"
        "├ 🔗 `m.facebook.com/...`\n"
        "└ 🔗 `web.facebook.com/...`\n\n"
        "❌ **Not Supported:**\n"
        "├ 🚫 Private videos\n"
        "├ 🚫 Live streams (ongoing)\n"
        "├ 🚫 Stories\n"
        "└ 🚫 Videos from other platforms\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 **Tip:** Make sure the video is set to `Public`.\n\n"
        f"⚡ {BOT_USERNAME}"
    )
    await update.message.reply_text(supported_text, parse_mode="Markdown")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name or "User"
    downloads = context.user_data.get("downloads", 0)
    joined = context.user_data.get("joined", "Today")

    stats_text = (
        "📊 **Your Stats**\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **User:** {first_name}\n"
        f"🆔 **ID:** `{user.id}`\n"
        f"📅 **First Used:** {joined}\n"
        f"📥 **Downloads:** {downloads}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Keep downloading! 🚀\n\n"
        f"⚡ {BOT_USERNAME}"
    )
    await update.message.reply_text(stats_text, parse_mode="Markdown")


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    msg = await update.message.reply_text("🏓 Pinging...")
    end_time = time.time()
    latency = round((end_time - start_time) * 1000)

    ping_text = (
        "🏓 **Pong!**\n\n"
        f"⚡ **Response Time:** `{latency}ms`\n"
        f"🟢 **Status:** Online\n"
        f"🕐 **Server Time:** `{time.strftime('%H:%M:%S UTC')}`\n\n"
        f"Bot is running smoothly! ✅"
    )
    await msg.edit_text(ping_text, parse_mode="Markdown")


# ==================== Message Handler ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()

    if not is_facebook_url(user_text):
        await update.message.reply_text(
            "🚫 **Invalid Link!**\n\n"
            "That doesn't look like a Facebook link.\n"
            "Please send a valid Facebook video or reel URL.\n\n"
            "💡 **Example:**\n"
            "`https://www.facebook.com/reel/569975832234512`\n\n"
            "Type /supported to see all supported link types.",
            parse_mode="Markdown",
        )
        return

    if "downloads" not in context.user_data:
        context.user_data["downloads"] = 0
        context.user_data["joined"] = time.strftime("%Y-%m-%d")

    processing_msg = await update.message.reply_text(
        "🔍 **Processing your link...**\n\n"
        "⏳ Fetching video details, please wait.",
        parse_mode="Markdown",
    )

    data = fetch_video_data(user_text)

    if not data or data.get("error", True):
        await processing_msg.edit_text(
            "❌ **Video Not Found!**\n\n"
            "Possible reasons:\n"
            "├ 🔒 The video is private\n"
            "├ 🗑️ The video has been deleted\n"
            "├ 🔗 The link is broken or invalid\n"
            "└ 🌐 Network issue on server side\n\n"
            "💡 Please check the link and try again.",
            parse_mode="Markdown",
        )
        return

    title = data.get("title", "Untitled Video")
    author = data.get("author", "Unknown")
    duration = format_duration(data.get("duration", 0))
    thumbnail = data.get("thumbnail", "")
    medias = data.get("medias", [])

    videos = [m for m in medias if m.get("type") == "video"]
    audios = [m for m in medias if m.get("type") == "audio"]

    if not videos and not audios:
        await processing_msg.edit_text(
            "❌ **No downloadable media found!**\n\n"
            "The link was recognized but no media could be extracted.",
            parse_mode="Markdown",
        )
        return

    # Get file sizes for each media
    await processing_msg.edit_text(
        "🔍 **Processing your link...**\n\n"
        "📦 Checking file sizes...",
        parse_mode="Markdown",
    )

    for media in videos + audios:
        size = get_file_size(media["url"])
        media["file_size"] = size
        media["file_size_label"] = format_file_size(size)

    context.user_data["video_data"] = {
        "title": title,
        "author": author,
        "videos": videos,
        "audios": audios,
        "thumbnail": thumbnail,
        "url": user_text,
    }

    # Build keyboard
    keyboard = []
    for i, video in enumerate(videos):
        quality = video.get("quality", "Unknown")
        ext = video.get("extension", "mp4").upper()
        icon = get_quality_icon(quality)
        size_label = video.get("file_size_label", "")
        size_text = f" • {size_label}" if size_label != "Unknown" else ""
        btn_text = f"{icon} {quality} ({ext}{size_text})"
        keyboard.append(
            [InlineKeyboardButton(btn_text, callback_data=f"video_{i}")]
        )

    for i, audio in enumerate(audios):
        ext = audio.get("extension", "mp3").upper()
        size_label = audio.get("file_size_label", "")
        size_text = f" • {size_label}" if size_label != "Unknown" else ""
        btn_text = f"🎵 Audio ({ext}{size_text})"
        keyboard.append(
            [InlineKeyboardButton(btn_text, callback_data=f"audio_{i}")]
        )

    keyboard.append(
        [InlineKeyboardButton("🔗 Open on Facebook", url=user_text)]
    )

    reply_markup = InlineKeyboardMarkup(keyboard)

    info_text = (
        "✅ **Video Found!**\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 **Title:** {title}\n"
        f"👤 **Author:** {author}\n"
        f"⏱️ **Duration:** {duration}\n"
        f"📦 **Formats:** {len(videos)} video, {len(audios)} audio\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 **Select your preferred quality:**"
    )

    await processing_msg.delete()

    if thumbnail:
        try:
            await update.message.reply_photo(
                photo=thumbnail,
                caption=info_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
        except Exception:
            await update.message.reply_text(
                info_text, reply_markup=reply_markup, parse_mode="Markdown"
            )
    else:
        await update.message.reply_text(
            info_text, reply_markup=reply_markup, parse_mode="Markdown"
        )


# ==================== Send Media Function ====================

async def send_media_file(context, chat_id, download_url, media_type, quality, video_data, extension):
    """ভিডিও/অডিও পাঠায় — ছোট হলে URL দিয়ে, বড় হলে ডাউনলোড করে"""

    icon = get_quality_icon(quality) if media_type == "video" else "🎵"

    caption_text = (
        f"✅ **Download Complete!**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 {video_data['title']}\n"
        f"👤 {video_data['author']}\n"
        f"{icon} Quality: **{quality}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ {BOT_USERNAME}"
    )

    # === Method 1: Try sending via URL (works for <50MB) ===
    try:
        if media_type == "video":
            await context.bot.send_video(
                chat_id=chat_id,
                video=download_url,
                caption=caption_text,
                parse_mode="Markdown",
                supports_streaming=True,
                read_timeout=120,
                write_timeout=120,
                connect_timeout=60,
            )
        elif media_type == "audio":
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=download_url,
                caption=caption_text,
                parse_mode="Markdown",
                read_timeout=120,
                write_timeout=120,
                connect_timeout=60,
            )
        return True, "url"
    except Exception as e:
        logger.warning(f"URL method failed: {e}")

    # === Method 2: Download to server, then upload as file ===
    try:
        temp_path = download_file_to_temp(download_url, extension)
        if not temp_path:
            return False, "download_failed"

        file_size = os.path.getsize(temp_path)
        logger.info(f"Downloaded file size: {format_file_size(file_size)}")

        # Telegram Bot API limit is 50MB for upload too,
        # but sending as document sometimes works for slightly larger files
        # For files up to 2GB, we use InputFile (local upload)

        if file_size > TELEGRAM_UPLOAD_LIMIT:
            cleanup_file(temp_path)
            return False, "too_large"

        with open(temp_path, "rb") as f:
            if media_type == "video":
                # Try as video first
                try:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=f,
                        caption=caption_text,
                        parse_mode="Markdown",
                        supports_streaming=True,
                        read_timeout=300,
                        write_timeout=300,
                        connect_timeout=120,
                    )
                    cleanup_file(temp_path)
                    return True, "upload_video"
                except Exception:
                    pass

                # If video fails, try as document
                f.seek(0)
                try:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        caption=caption_text,
                        parse_mode="Markdown",
                        filename=f"facebook_{quality}.{extension}",
                        read_timeout=300,
                        write_timeout=300,
                        connect_timeout=120,
                    )
                    cleanup_file(temp_path)
                    return True, "upload_document"
                except Exception as e2:
                    logger.error(f"Document upload also failed: {e2}")

            elif media_type == "audio":
                try:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=f,
                        caption=caption_text,
                        parse_mode="Markdown",
                        filename=f"facebook_audio.{extension}",
                        read_timeout=300,
                        write_timeout=300,
                        connect_timeout=120,
                    )
                    cleanup_file(temp_path)
                    return True, "upload_audio"
                except Exception:
                    # Try as document
                    f.seek(0)
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        caption=caption_text,
                        parse_mode="Markdown",
                        filename=f"facebook_audio.{extension}",
                        read_timeout=300,
                        write_timeout=300,
                        connect_timeout=120,
                    )
                    cleanup_file(temp_path)
                    return True, "upload_audio_doc"

        cleanup_file(temp_path)
        return False, "upload_failed"

    except Exception as e:
        logger.error(f"Upload method failed: {e}")
        if 'temp_path' in locals():
            cleanup_file(temp_path)
        return False, "error"


# ==================== Callback Handler ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # === Info callbacks ===
    if data == "cb_help":
        help_text = (
            "📖 **How to Use**\n\n"
            "**Step 1️⃣** — Copy a Facebook video link\n"
            "**Step 2️⃣** — Paste it here in chat\n"
            "**Step 3️⃣** — Choose quality (HD / SD / Audio)\n"
            "**Step 4️⃣** — Receive your file! 🎉\n\n"
            "✨ Works with videos of **any size!**\n\n"
            f"⚡ {BOT_USERNAME}"
        )
        back_btn = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back", callback_data="cb_back_start")]]
        )
        await query.edit_message_text(
            help_text, parse_mode="Markdown", reply_markup=back_btn
        )
        return

    if data == "cb_supported":
        sup_text = (
            "📋 **Supported Links**\n\n"
            "✅ `facebook.com/watch/...`\n"
            "✅ `facebook.com/reel/...`\n"
            "✅ `facebook.com/video/...`\n"
            "✅ `fb.watch/...`\n"
            "✅ `m.facebook.com/...`\n\n"
            "❌ Private / Stories / Live\n\n"
            f"⚡ {BOT_USERNAME}"
        )
        back_btn = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back", callback_data="cb_back_start")]]
        )
        await query.edit_message_text(
            sup_text, parse_mode="Markdown", reply_markup=back_btn
        )
        return

    if data == "cb_about":
        about_text = (
            "ℹ️ **About**\n\n"
            f"🤖 {BOT_USERNAME}\n"
            "📌 Version: 3.0\n"
            "🆓 Free & No Size Limit\n\n"
            "Features: HD/SD Video, Audio, Any File Size!\n\n"
            "Made with ❤️"
        )
        back_btn = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back", callback_data="cb_back_start")]]
        )
        await query.edit_message_text(
            about_text, parse_mode="Markdown", reply_markup=back_btn
        )
        return

    if data == "cb_ping":
        ping_text = (
            f"🏓 **Pong!**\n\n"
            f"🟢 **Status:** Online\n"
            f"🕐 **Time:** `{time.strftime('%H:%M:%S UTC')}`\n\n"
            f"Bot is running! ✅"
        )
        back_btn = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back", callback_data="cb_back_start")]]
        )
        await query.edit_message_text(
            ping_text, parse_mode="Markdown", reply_markup=back_btn
        )
        return

    if data == "cb_back_start":
        user = update.effective_user
        first_name = user.first_name or "User"
        welcome_text = (
            f"Hey **{first_name}**! 👋\n\n"
            f"Welcome to **Facebook Video Downloader** 🎬\n\n"
            f"I can download videos, reels & audio from Facebook — "
            f"**any size, any quality!** 🚀\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 Send me any Facebook video link\n"
            f"🔹 Choose your preferred quality\n"
            f"🔹 Get your video instantly!\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✨ **No size limit** — even 100MB+ videos!\n\n"
            f"💡 Type /help for detailed instructions.\n\n"
            f"⚡ Powered by {BOT_USERNAME}"
        )
        keyboard = [
            [
                InlineKeyboardButton("📖 How to Use", callback_data="cb_help"),
                InlineKeyboardButton("📋 Supported Links", callback_data="cb_supported"),
            ],
            [
                InlineKeyboardButton("ℹ️ About", callback_data="cb_about"),
                InlineKeyboardButton("🏓 Ping", callback_data="cb_ping"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            welcome_text, parse_mode="Markdown", reply_markup=reply_markup
        )
        return

    # === Download callbacks ===
    video_data = context.user_data.get("video_data")

    if not video_data:
        await query.answer("⚠️ Session expired! Send the link again.", show_alert=True)
        return

    download_url = None
    media_type = None
    quality = None
    extension = "mp4"

    if data.startswith("video_"):
        index = int(data.split("_")[1])
        videos = video_data.get("videos", [])
        if index < len(videos):
            download_url = videos[index]["url"]
            quality = videos[index].get("quality", "Unknown")
            extension = videos[index].get("extension", "mp4")
            media_type = "video"

    elif data.startswith("audio_"):
        index = int(data.split("_")[1])
        audios = video_data.get("audios", [])
        if index < len(audios):
            download_url = audios[index]["url"]
            quality = "Audio"
            extension = audios[index].get("extension", "mp3")
            media_type = "audio"

    if not download_url:
        await query.answer("❌ Download link not found!", show_alert=True)
        return

    icon = get_quality_icon(quality) if media_type == "video" else "🎵"

    # Update status
    try:
        await query.edit_message_caption(
            caption=(
                f"⬇️ **Downloading & Uploading...**\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{icon} Quality: **{quality}**\n"
                f"📌 {video_data['title']}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⏳ This may take a moment for large files.\n"
                f"Please don't send another link until this is done."
            ),
            parse_mode="Markdown",
        )
    except Exception:
        pass

    # Send the media
    success, method = await send_media_file(
        context, query.message.chat_id, download_url,
        media_type, quality, video_data, extension
    )

    if success:
        context.user_data["downloads"] = context.user_data.get("downloads", 0) + 1

        method_label = {
            "url": "⚡ Direct",
            "upload_video": "📤 Server Upload (Video)",
            "upload_document": "📤 Server Upload (Document)",
            "upload_audio": "📤 Server Upload (Audio)",
            "upload_audio_doc": "📤 Server Upload (Document)",
        }.get(method, "Unknown")

        try:
            await query.edit_message_caption(
                caption=(
                    f"✅ **Sent Successfully!**\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 {video_data['title']}\n"
                    f"{icon} Quality: **{quality}**\n"
                    f"📡 Method: {method_label}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📥 Total Downloads: {context.user_data['downloads']}\n\n"
                    f"Send another link to download more! 🔗"
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass
    else:
        # All methods failed — give direct download link
        fallback_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⬇️ Download {quality} Directly", url=download_url)],
            [InlineKeyboardButton("🔗 Open on Facebook", url=video_data.get("url", ""))],
        ])

        try:
            await query.edit_message_caption(
                caption=(
                    f"📥 **Direct Download Link**\n\n"
                    f"The file couldn't be sent via Telegram.\n"
                    f"Please use the button below to download.\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 {video_data['title']}\n"
                    f"{icon} Quality: **{quality}**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"💡 Tap the button → Download → Enjoy!\n\n"
                    f"⚡ {BOT_USERNAME}"
                ),
                reply_markup=fallback_keyboard,
                parse_mode="Markdown",
            )
        except Exception:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    f"📥 **Direct Download Link**\n\n"
                    f"Tap the button below to download your file.\n"
                ),
                reply_markup=fallback_keyboard,
                parse_mode="Markdown",
            )


# ==================== Error Handler ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ **Oops! Something went wrong.**\n\n"
                "Please try again later or send a different link.\n\n"
                f"⚡ {BOT_USERNAME}",
                parse_mode="Markdown",
            )
        except Exception:
            pass


# ==================== Post Init ====================

async def post_init(application):
    await set_bot_commands(application)
    logger.info("Bot commands set successfully!")


# ==================== Main ====================

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        return

    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask server started on port {PORT}")

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .read_timeout(300)
        .write_timeout(300)
        .connect_timeout(120)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("supported", supported_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)

    logger.info("🚀 Bot is starting...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
