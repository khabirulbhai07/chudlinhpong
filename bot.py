import os
import logging
import requests
import json
import time
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


def get_file_size_label(quality: str) -> str:
    icons = {"HD": "🔵", "SD": "🟢", "Audio": "🟣"}
    return icons.get(quality, "⚪")


# ==================== Bot Commands ====================

async def set_bot_commands(application):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "How to use this bot"),
        BotCommand("about", "About this bot"),
        BotCommand("supported", "Supported link types"),
        BotCommand("stats", "Your usage stats"),
        BotCommand("ping", "Check bot status"),
    ]
    await application.bot.set_my_commands(commands)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name or "User"

    # Initialize user stats
    if "downloads" not in context.user_data:
        context.user_data["downloads"] = 0
        context.user_data["joined"] = time.strftime("%Y-%m-%d")

    welcome_text = (
        f"Hey **{first_name}**! 👋\n\n"
        f"Welcome to **Facebook Video Downloader** 🎬\n\n"
        f"I can download videos, reels & audio from Facebook in just seconds.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔹 Send me any Facebook video link\n"
        f"🔹 Choose your preferred quality\n"
        f"🔹 Get your video instantly!\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
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
        "**Step 1️⃣** — Open Facebook & find the video you want\n"
        "**Step 2️⃣** — Tap `Share` → `Copy Link`\n"
        "**Step 3️⃣** — Paste the link here in chat\n"
        "**Step 4️⃣** — Select quality (HD / SD / Audio)\n"
        "**Step 5️⃣** — Done! Your file will be sent 🎉\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 **Commands:**\n"
        "/start — Start the bot\n"
        "/help — How to use\n"
        "/about — About this bot\n"
        "/supported — Supported link types\n"
        "/stats — Your download stats\n"
        "/ping — Check if bot is alive\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ **Note:** Only public videos can be downloaded. "
        "Private or restricted videos are not supported.\n\n"
        f"⚡ {BOT_USERNAME}"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    about_text = (
        "ℹ️ **About This Bot**\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 **Bot:** {BOT_USERNAME}\n"
        "📌 **Version:** 2.0\n"
        "🔧 **Language:** Python\n"
        "🌐 **API:** ZylaLabs\n"
        "☁️ **Hosted on:** Render\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 **Features:**\n"
        "├ 📹 Download FB Videos\n"
        "├ 🎞️ Download FB Reels\n"
        "├ 🔵 HD Quality Support\n"
        "├ 🟢 SD Quality Support\n"
        "├ 🎵 Audio Extraction\n"
        "├ 🖼️ Thumbnail Preview\n"
        "├ ⚡ Fast & Reliable\n"
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
        "💡 **Tip:** Make sure the video is set to `Public` "
        "before copying the link.\n\n"
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

    # Initialize stats
    if "downloads" not in context.user_data:
        context.user_data["downloads"] = 0
        context.user_data["joined"] = time.strftime("%Y-%m-%d")

    processing_msg = await update.message.reply_text(
        "🔍 **Processing your link...**\n\n"
        "⏳ Fetching video details, please wait."
        , parse_mode="Markdown"
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
            "The link was recognized but no video/audio could be extracted.",
            parse_mode="Markdown",
        )
        return

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
        icon = get_file_size_label(quality)
        btn_text = f"{icon} {quality} Quality ({ext})"
        keyboard.append(
            [InlineKeyboardButton(btn_text, callback_data=f"video_{i}")]
        )

    for i, audio in enumerate(audios):
        ext = audio.get("extension", "mp3").upper()
        btn_text = f"🎵 Audio Only ({ext})"
        keyboard.append(
            [InlineKeyboardButton(btn_text, callback_data=f"audio_{i}")]
        )

    # Add download all via link button
    if videos:
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
        f"📦 **Available Formats:** {len(videos)} video, {len(audios)} audio\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 **Select your preferred quality below:**"
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


# ==================== Callback Handler ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Handle info callbacks from start menu
    if data == "cb_help":
        help_text = (
            "📖 **How to Use**\n\n"
            "**Step 1️⃣** — Copy a Facebook video link\n"
            "**Step 2️⃣** — Paste it here in chat\n"
            "**Step 3️⃣** — Choose quality (HD / SD / Audio)\n"
            "**Step 4️⃣** — Receive your file! 🎉\n\n"
            "It's that simple! 😊\n\n"
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
            "📌 Version: 2.0\n"
            "🆓 Free & Open Source\n\n"
            "Features: HD/SD Video, Audio, Fast Downloads\n\n"
            "Made with ❤️"
        )
        back_btn = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back", callback_data="cb_back_start")]]
        )
        await query.edit_message_text(
            about_text, parse_mode="Markdown", reply_markup=back_btn
        )
        return

    if data == "cb_back_start":
        user = update.effective_user
        first_name = user.first_name or "User"
        welcome_text = (
            f"Hey **{first_name}**! 👋\n\n"
            f"Welcome to **Facebook Video Downloader** 🎬\n\n"
            f"I can download videos, reels & audio from Facebook in just seconds.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 Send me any Facebook video link\n"
            f"🔹 Choose your preferred quality\n"
            f"🔹 Get your video instantly!\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💡 Type /help for detailed instructions.\n\n"
            f"⚡ Powered by {BOT_USERNAME}"
        )
        keyboard = [
            [
                InlineKeyboardButton("📖 How to Use", callback_data="cb_help"),
                InlineKeyboardButton("📋 Supported Links", callback_data="cb_supported"),
            ],
            [InlineKeyboardButton("ℹ️ About", callback_data="cb_about")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            welcome_text, parse_mode="Markdown", reply_markup=reply_markup
        )
        return

    # Handle video/audio download callbacks
    video_data = context.user_data.get("video_data")

    if not video_data:
        await query.answer("⚠️ Session expired! Please send the link again.", show_alert=True)
        return

    download_url = None
    media_type = None
    quality = None

    if data.startswith("video_"):
        index = int(data.split("_")[1])
        videos = video_data.get("videos", [])
        if index < len(videos):
            download_url = videos[index]["url"]
            quality = videos[index].get("quality", "Unknown")
            media_type = "video"

    elif data.startswith("audio_"):
        index = int(data.split("_")[1])
        audios = video_data.get("audios", [])
        if index < len(audios):
            download_url = audios[index]["url"]
            quality = "Audio"
            media_type = "audio"

    if not download_url:
        await query.answer("❌ Download link not found!", show_alert=True)
        return

    icon = get_file_size_label(quality) if media_type == "video" else "🎵"

    try:
        # Update caption to show downloading status
        try:
            await query.edit_message_caption(
                caption=(
                    f"⬇️ **Downloading {quality}...**\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"{icon} Quality: **{quality}**\n"
                    f"📌 {video_data['title']}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⏳ Uploading to Telegram, please wait..."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass

        if media_type == "video":
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=download_url,
                caption=(
                    f"✅ **Download Complete!**\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 {video_data['title']}\n"
                    f"👤 {video_data['author']}\n"
                    f"{icon} Quality: **{quality}**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⚡ {BOT_USERNAME}"
                ),
                parse_mode="Markdown",
                supports_streaming=True,
                read_timeout=120,
                write_timeout=120,
                connect_timeout=60,
            )
        elif media_type == "audio":
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=download_url,
                caption=(
                    f"✅ **Download Complete!**\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 {video_data['title']}\n"
                    f"🎵 Format: Audio\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⚡ {BOT_USERNAME}"
                ),
                parse_mode="Markdown",
                read_timeout=120,
                write_timeout=120,
                connect_timeout=60,
            )

        # Update download count
        context.user_data["downloads"] = context.user_data.get("downloads", 0) + 1

        # Update the original message
        try:
            await query.edit_message_caption(
                caption=(
                    f"✅ **Sent Successfully!**\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 {video_data['title']}\n"
                    f"{icon} Quality: **{quality}**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📥 Total Downloads: {context.user_data['downloads']}\n\n"
                    f"Send another link to download more! 🔗"
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Send error: {e}")

        fallback_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⬇️ Download {quality}", url=download_url)],
            [InlineKeyboardButton("🔗 Open on Facebook", url=video_data.get("url", ""))],
        ])

        try:
            await query.edit_message_caption(
                caption=(
                    f"⚠️ **File Too Large for Telegram!**\n\n"
                    f"The {quality} file exceeds Telegram's 50MB limit.\n"
                    f"Use the button below to download directly.\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 {video_data['title']}\n"
                    f"{icon} Quality: **{quality}**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⚡ {BOT_USERNAME}"
                ),
                reply_markup=fallback_keyboard,
                parse_mode="Markdown",
            )
        except Exception:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    f"⚠️ **File Too Large!**\n\n"
                    f"Use the button below to download directly.\n"
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
    logger.info("✅ Bot commands have been set!")


# ==================== Main ====================

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        return

    # Start Flask in background
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask server started on port {PORT}")

    # Build application
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .read_timeout(120)
        .write_timeout(120)
        .connect_timeout(60)
        .post_init(post_init)
        .build()
    )

    # Add handlers
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
