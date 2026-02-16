import os
import logging
import requests
import json
import time
import tempfile
import asyncio
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

# ==================== Logging ====================
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

# ==================== Helpers ====================

def is_facebook_url(url: str) -> bool:
    fb = ["facebook.com", "fb.com", "fb.watch", "www.facebook.com", "m.facebook.com", "web.facebook.com"]
    return any(d in url.lower() for d in fb)


def fetch_video_data(fb_url: str) -> dict:
    headers = {"Authorization": f"Bearer {ZYLA_API_KEY}", "Content-Type": "application/json"}
    payload = json.dumps({"url": fb_url})
    try:
        r = requests.post(ZYLA_API_URL, headers=headers, data=payload, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"API Error: {e}")
        return None


def format_duration(ms):
    if not ms:
        return "N/A"
    s = ms // 1000
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if h:
        return f"{h}h {m}m {s}s"
    elif m:
        return f"{m}m {s}s"
    return f"{s}s"


def get_quality_icon(q):
    return {"HD": "🔵", "SD": "🟢", "Audio": "🟣"}.get(q, "⚪")


def get_file_size(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=10)
        return int(r.headers.get("content-length", 0))
    except:
        return 0


def format_size(b):
    if b <= 0:
        return "Unknown"
    for u in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"


def download_to_temp(url, ext="mp4", progress_callback=None):
    """ফাইল ডাউনলোড করে temp এ সেভ করে"""
    try:
        r = requests.get(url, stream=True, timeout=600)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}", dir=tempfile.gettempdir())
        downloaded = 0
        chunk_size = 2 * 1024 * 1024  # 2MB chunks

        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                tmp.write(chunk)
                downloaded += len(chunk)

        tmp.close()
        logger.info(f"Downloaded {format_size(downloaded)} -> {tmp.name}")
        return tmp.name, downloaded
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None, 0


def cleanup(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except:
        pass


# ==================== Upload Function ====================

async def upload_media(context, chat_id, url, media_type, quality, video_data, ext, status_callback=None):
    """
    3-Step Upload System:
    1. URL দিয়ে চেষ্টা (≤50MB)
    2. ডাউনলোড করে Video হিসেবে আপলোড
    3. ডাউনলোড করে Document হিসেবে আপলোড (≤2GB)
    """
    
    icon = get_quality_icon(quality) if media_type == "video" else "🎵"
    caption = (
        f"✅ **Download Complete!**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 {video_data['title']}\n"
        f"👤 {video_data['author']}\n"
        f"{icon} Quality: **{quality}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ {BOT_USERNAME}"
    )

    # ========== STEP 1: URL Method (Fast, ≤50MB) ==========
    try:
        if status_callback:
            await status_callback("⚡ **Sending via fast method...**")
        
        if media_type == "video":
            await context.bot.send_video(
                chat_id=chat_id, video=url, caption=caption,
                parse_mode="Markdown", supports_streaming=True,
                read_timeout=120, write_timeout=120,
            )
        else:
            await context.bot.send_audio(
                chat_id=chat_id, audio=url, caption=caption,
                parse_mode="Markdown",
                read_timeout=120, write_timeout=120,
            )
        return True, "direct"
    except Exception as e:
        logger.info(f"URL method failed (expected for >50MB): {e}")

    # ========== STEP 2 & 3: Download + Upload ==========
    if status_callback:
        await status_callback("📥 **Downloading to server...**\n⏳ Large file detected, this may take a while.")

    temp_path, file_size = download_to_temp(url, ext)
    
    if not temp_path:
        return False, "download_failed"

    logger.info(f"File downloaded: {format_size(file_size)}")

    if status_callback:
        await status_callback(
            f"📤 **Uploading to Telegram...**\n"
            f"📦 Size: **{format_size(file_size)}**\n"
            f"⏳ Please wait, uploading large file..."
        )

    # ========== STEP 2: Upload as Video ==========
    try:
        with open(temp_path, "rb") as f:
            if media_type == "video":
                await context.bot.send_video(
                    chat_id=chat_id, video=f, caption=caption,
                    parse_mode="Markdown", supports_streaming=True,
                    filename=f"FB_{quality}_{int(time.time())}.{ext}",
                    read_timeout=600, write_timeout=600, connect_timeout=120,
                )
            else:
                await context.bot.send_audio(
                    chat_id=chat_id, audio=f, caption=caption,
                    parse_mode="Markdown",
                    filename=f"FB_Audio_{int(time.time())}.{ext}",
                    read_timeout=600, write_timeout=600, connect_timeout=120,
                )
        cleanup(temp_path)
        return True, "upload_media"
    except Exception as e:
        logger.warning(f"Media upload failed, trying document: {e}")

    # ========== STEP 3: Upload as Document (supports up to 2GB) ==========
    try:
        if status_callback:
            await status_callback(
                f"📄 **Uploading as document...**\n"
                f"📦 Size: **{format_size(file_size)}**\n"
                f"⏳ Almost there..."
            )

        with open(temp_path, "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id, document=f, caption=caption,
                parse_mode="Markdown",
                filename=f"Facebook_{quality}_{int(time.time())}.{ext}",
                read_timeout=600, write_timeout=600, connect_timeout=120,
            )
        cleanup(temp_path)
        return True, "upload_document"
    except Exception as e:
        logger.error(f"Document upload failed: {e}")

    cleanup(temp_path)
    return False, "all_failed"


# ==================== Bot Commands ====================

async def set_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "🚀 Start the bot"),
        BotCommand("help", "📖 How to use this bot"),
        BotCommand("about", "ℹ️ About this bot"),
        BotCommand("supported", "📋 Supported link types"),
        BotCommand("stats", "📊 Your usage stats"),
        BotCommand("ping", "🏓 Check bot status"),
    ])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "User"

    if "downloads" not in context.user_data:
        context.user_data["downloads"] = 0
        context.user_data["joined"] = time.strftime("%Y-%m-%d")

    text = (
        f"Hey **{name}**! 👋\n\n"
        f"Welcome to **Facebook Video Downloader** 🎬\n\n"
        f"Download videos, reels & audio from Facebook\n"
        f"— **Any size, any quality, no limits!** 🚀\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔹 Send any Facebook video link\n"
        f"🔹 Choose quality (HD / SD / Audio)\n"
        f"🔹 Get your file instantly!\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 **No file size limit!**\n"
        f"Even 100MB, 200MB, 500MB+ videos work!\n\n"
        f"⚡ Powered by {BOT_USERNAME}"
    )

    kb = [
        [
            InlineKeyboardButton("📖 How to Use", callback_data="cb_help"),
            InlineKeyboardButton("📋 Supported", callback_data="cb_supported"),
        ],
        [
            InlineKeyboardButton("ℹ️ About", callback_data="cb_about"),
            InlineKeyboardButton("🏓 Ping", callback_data="cb_ping"),
        ],
    ]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 **How to Use**\n\n"
        "**Step 1️⃣** — Open Facebook & find the video\n"
        "**Step 2️⃣** — Tap `Share` → `Copy Link`\n"
        "**Step 3️⃣** — Paste the link here\n"
        "**Step 4️⃣** — Select quality\n"
        "**Step 5️⃣** — Receive your file! 🎉\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 **Commands:**\n"
        "/start — 🚀 Start the bot\n"
        "/help — 📖 How to use\n"
        "/about — ℹ️ About this bot\n"
        "/supported — 📋 Supported links\n"
        "/stats — 📊 Your download stats\n"
        "/ping — 🏓 Check bot status\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📦 **Large files:** Downloaded to server first,\n"
        "then uploaded to Telegram. May take 1-3 mins.\n\n"
        f"⚡ {BOT_USERNAME}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ **About This Bot**\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 **Bot:** {BOT_USERNAME}\n"
        "📌 **Version:** 3.0\n"
        "🔧 **Language:** Python\n"
        "🌐 **API:** ZylaLabs\n"
        "☁️ **Hosted:** Render\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 **Features:**\n"
        "├ 📹 FB Videos & Reels\n"
        "├ 🔵 HD / 🟢 SD Quality\n"
        "├ 🎵 Audio Extraction\n"
        "├ 🖼️ Thumbnail Preview\n"
        "├ 📦 File Size Info\n"
        "├ 🚫 No Size Limit\n"
        "├ ⚡ Fast Downloads\n"
        "└ 🆓 Completely Free\n\n"
        f"Made with ❤️ | {BOT_USERNAME}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def supported_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 **Supported Link Types**\n\n"
        "✅ **Works:**\n"
        "├ 🔗 `facebook.com/watch/...`\n"
        "├ 🔗 `facebook.com/reel/...`\n"
        "├ 🔗 `facebook.com/video/...`\n"
        "├ 🔗 `facebook.com/share/v/...`\n"
        "├ 🔗 `fb.watch/...`\n"
        "├ 🔗 `m.facebook.com/...`\n"
        "└ 🔗 `web.facebook.com/...`\n\n"
        "❌ **Doesn't Work:**\n"
        "├ 🚫 Private videos\n"
        "├ 🚫 Live streams\n"
        "├ 🚫 Stories\n"
        "└ 🚫 Other platforms\n\n"
        f"⚡ {BOT_USERNAME}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    dl = context.user_data.get("downloads", 0)
    joined = context.user_data.get("joined", "Today")
    text = (
        "📊 **Your Stats**\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **User:** {user.first_name}\n"
        f"🆔 **ID:** `{user.id}`\n"
        f"📅 **First Used:** {joined}\n"
        f"📥 **Downloads:** {dl}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ {BOT_USERNAME}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t1 = time.time()
    msg = await update.message.reply_text("🏓 Pinging...")
    ms = round((time.time() - t1) * 1000)
    await msg.edit_text(
        f"🏓 **Pong!**\n\n"
        f"⚡ Latency: `{ms}ms`\n"
        f"🟢 Status: Online\n"
        f"🕐 Time: `{time.strftime('%H:%M:%S UTC')}`",
        parse_mode="Markdown",
    )


# ==================== Message Handler ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not is_facebook_url(url):
        await update.message.reply_text(
            "🚫 **Invalid Link!**\n\n"
            "Send a valid Facebook video/reel link.\n\n"
            "💡 Example:\n`https://www.facebook.com/reel/569975832234512`",
            parse_mode="Markdown",
        )
        return

    if "downloads" not in context.user_data:
        context.user_data["downloads"] = 0
        context.user_data["joined"] = time.strftime("%Y-%m-%d")

    msg = await update.message.reply_text(
        "🔍 **Processing...**\n⏳ Fetching video details.",
        parse_mode="Markdown",
    )

    data = fetch_video_data(url)

    if not data or data.get("error", True):
        await msg.edit_text(
            "❌ **Video Not Found!**\n\n"
            "├ 🔒 Video might be private\n"
            "├ 🗑️ Might be deleted\n"
            "└ 🔗 Link might be invalid\n\n"
            "💡 Check the link and try again.",
            parse_mode="Markdown",
        )
        return

    title = data.get("title", "Untitled")
    author = data.get("author", "Unknown")
    duration = format_duration(data.get("duration", 0))
    thumb = data.get("thumbnail", "")
    medias = data.get("medias", [])

    videos = [m for m in medias if m.get("type") == "video"]
    audios = [m for m in medias if m.get("type") == "audio"]

    if not videos and not audios:
        await msg.edit_text("❌ No downloadable media found!", parse_mode="Markdown")
        return

    await msg.edit_text("📦 **Checking file sizes...**", parse_mode="Markdown")

    for m in videos + audios:
        sz = get_file_size(m["url"])
        m["size"] = sz
        m["size_label"] = format_size(sz)

    context.user_data["video_data"] = {
        "title": title, "author": author,
        "videos": videos, "audios": audios,
        "thumbnail": thumb, "url": url,
    }

    kb = []
    for i, v in enumerate(videos):
        q = v.get("quality", "?")
        ext = v.get("extension", "mp4").upper()
        icon = get_quality_icon(q)
        sl = v.get("size_label", "")
        st = f" • {sl}" if sl != "Unknown" else ""
        kb.append([InlineKeyboardButton(f"{icon} {q} ({ext}{st})", callback_data=f"v_{i}")])

    for i, a in enumerate(audios):
        ext = a.get("extension", "mp3").upper()
        sl = a.get("size_label", "")
        st = f" • {sl}" if sl != "Unknown" else ""
        kb.append([InlineKeyboardButton(f"🎵 Audio ({ext}{st})", callback_data=f"a_{i}")])

    kb.append([InlineKeyboardButton("🔗 Open on Facebook", url=url)])

    info = (
        "✅ **Video Found!**\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 **Title:** {title}\n"
        f"👤 **Author:** {author}\n"
        f"⏱️ **Duration:** {duration}\n"
        f"📦 **Formats:** {len(videos)} video, {len(audios)} audio\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 **Select quality:**"
    )

    await msg.delete()

    if thumb:
        try:
            await update.message.reply_photo(
                photo=thumb, caption=info,
                reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown",
            )
            return
        except:
            pass

    await update.message.reply_text(
        info, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown",
    )


# ==================== Callback Handler ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = query.data

    # === Menu Callbacks ===
    if d == "cb_help":
        await query.edit_message_text(
            "📖 **How to Use**\n\n"
            "1️⃣ Copy Facebook video link\n"
            "2️⃣ Paste here\n"
            "3️⃣ Choose quality\n"
            "4️⃣ Get your file! 🎉\n\n"
            f"📦 No size limit!\n\n⚡ {BOT_USERNAME}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cb_back")]]),
        )
        return

    if d == "cb_supported":
        await query.edit_message_text(
            "📋 **Supported Links**\n\n"
            "✅ facebook.com/watch\n✅ facebook.com/reel\n"
            "✅ facebook.com/video\n✅ fb.watch\n✅ m.facebook.com\n\n"
            f"❌ Private / Stories / Live\n\n⚡ {BOT_USERNAME}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cb_back")]]),
        )
        return

    if d == "cb_about":
        await query.edit_message_text(
            f"ℹ️ **About**\n\n🤖 {BOT_USERNAME}\n📌 v3.0\n"
            f"🚫 No Size Limit\n🆓 Free Forever\n\nMade with ❤️",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cb_back")]]),
        )
        return

    if d == "cb_ping":
        await query.edit_message_text(
            f"🏓 **Pong!**\n🟢 Online\n🕐 {time.strftime('%H:%M:%S UTC')}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cb_back")]]),
        )
        return

    if d == "cb_back":
        user = update.effective_user
        kb = [
            [
                InlineKeyboardButton("📖 How to Use", callback_data="cb_help"),
                InlineKeyboardButton("📋 Supported", callback_data="cb_supported"),
            ],
            [
                InlineKeyboardButton("ℹ️ About", callback_data="cb_about"),
                InlineKeyboardButton("🏓 Ping", callback_data="cb_ping"),
            ],
        ]
        await query.edit_message_text(
            f"Hey **{user.first_name}**! 👋\n\n"
            f"**Facebook Video Downloader** 🎬\n\n"
            f"Send any FB video link to download!\n"
            f"📦 No size limit!\n\n⚡ {BOT_USERNAME}",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    # === Download Callbacks ===
    vd = context.user_data.get("video_data")
    if not vd:
        await query.answer("⚠️ Session expired! Send link again.", show_alert=True)
        return

    dl_url = None
    mtype = None
    quality = None
    ext = "mp4"

    if d.startswith("v_"):
        idx = int(d.split("_")[1])
        vs = vd.get("videos", [])
        if idx < len(vs):
            dl_url = vs[idx]["url"]
            quality = vs[idx].get("quality", "?")
            ext = vs[idx].get("extension", "mp4")
            mtype = "video"
            file_size = vs[idx].get("size", 0)

    elif d.startswith("a_"):
        idx = int(d.split("_")[1])
        aus = vd.get("audios", [])
        if idx < len(aus):
            dl_url = aus[idx]["url"]
            quality = "Audio"
            ext = aus[idx].get("extension", "mp3")
            mtype = "audio"
            file_size = aus[idx].get("size", 0)

    if not dl_url:
        await query.answer("❌ Link not found!", show_alert=True)
        return

    icon = get_quality_icon(quality) if mtype == "video" else "🎵"

    # Status update function
    async def update_status(text):
        try:
            await query.edit_message_caption(
                caption=f"{text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{icon} **{quality}**\n"
                f"📌 {vd['title']}\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                parse_mode="Markdown",
            )
        except:
            pass

    await update_status("⬇️ **Starting download...**")

    success, method = await upload_media(
        context, query.message.chat_id, dl_url,
        mtype, quality, vd, ext, update_status,
    )

    if success:
        context.user_data["downloads"] = context.user_data.get("downloads", 0) + 1

        method_labels = {
            "direct": "⚡ Direct",
            "upload_media": "📤 Server Upload",
            "upload_document": "📄 Document Upload",
        }

        try:
            await query.edit_message_caption(
                caption=(
                    f"✅ **Sent Successfully!**\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 {vd['title']}\n"
                    f"{icon} Quality: **{quality}**\n"
                    f"📡 Method: {method_labels.get(method, method)}\n"
                    f"📥 Downloads: {context.user_data['downloads']}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Send another link! 🔗"
                ),
                parse_mode="Markdown",
            )
        except:
            pass
    else:
        # Fallback: Direct download button
        fb_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⬇️ Download {quality}", url=dl_url)],
            [InlineKeyboardButton("🔗 Facebook", url=vd.get("url", ""))],
        ])
        try:
            await query.edit_message_caption(
                caption=(
                    f"📥 **Direct Download Link**\n\n"
                    f"Couldn't upload via Telegram.\n"
                    f"Tap the button to download directly!\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 {vd['title']}\n"
                    f"{icon} Quality: **{quality}**\n"
                    f"📦 Size: **{format_size(file_size)}**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⚡ {BOT_USERNAME}"
                ),
                reply_markup=fb_kb, parse_mode="Markdown",
            )
        except:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"📥 Download directly:", reply_markup=fb_kb,
            )


# ==================== Error Handler ====================

async def error_handler(update, context):
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"⚠️ Something went wrong. Try again.\n\n⚡ {BOT_USERNAME}",
                parse_mode="Markdown",
            )
        except:
            pass


# ==================== Post Init ====================

async def post_init(app):
    await set_bot_commands(app)
    logger.info("Bot commands set!")


# ==================== Main ====================

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return

    Thread(target=run_flask, daemon=True).start()
    logger.info(f"Flask on port {PORT}")

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .read_timeout(600)
        .write_timeout(600)
        .connect_timeout(120)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("supported", supported_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)

    logger.info("🚀 Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
