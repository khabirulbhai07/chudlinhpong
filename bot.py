import os
import logging
import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ZYLA_API_KEY = os.environ.get("ZYLA_API_KEY", "12368|FQZM8X1GtUdl98NngHB9tcM2Ff5caNkaoyiXAF7E")
PORT = int(os.environ.get("PORT", 10000))

# Zyla API URL
ZYLA_API_URL = "https://zylalabs.com/api/4146/facebook+download+api/7134/downloader"

# ==================== Flask Keep-Alive Server ====================
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "✅ Facebook Video Downloader Bot is Running!"

@app_flask.route("/health")
def health():
    return "OK", 200

def run_flask():
    app_flask.run(host="0.0.0.0", port=PORT)

# ==================== Helper Functions ====================

def is_facebook_url(url: str) -> bool:
    """চেক করে যে URL টি Facebook এর কিনা"""
    fb_domains = [
        "facebook.com",
        "fb.com",
        "fb.watch",
        "www.facebook.com",
        "m.facebook.com",
        "web.facebook.com",
    ]
    for domain in fb_domains:
        if domain in url:
            return True
    return False


def fetch_video_data(fb_url: str) -> dict:
    """Zyla API থেকে ভিডিও ডাটা নিয়ে আসে"""
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
    """মিলিসেকেন্ড থেকে মিনিট:সেকেন্ড ফরম্যাটে কনভার্ট করে"""
    if not ms:
        return "Unknown"
    seconds = ms // 1000
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


# ==================== Bot Command Handlers ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start কমান্ড হ্যান্ডলার"""
    welcome_text = (
        "🎬 **Facebook Video Downloader Bot**\n\n"
        "স্বাগতম! আমি Facebook ভিডিও ডাউনলোড করতে সাহায্য করি।\n\n"
        "📌 **কিভাবে ব্যবহার করবেন:**\n"
        "যেকোনো Facebook ভিডিও/Reel এর লিংক পাঠান, আমি আপনাকে "
        "HD ও SD কোয়ালিটিতে ডাউনলোড লিংক দেবো।\n\n"
        "🔗 **সাপোর্টেড লিংক:**\n"
        "• Facebook Video\n"
        "• Facebook Reel\n"
        "• Facebook Watch\n"
        "• fb.watch short links\n\n"
        "👇 এখন একটি Facebook ভিডিও লিংক পাঠান!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help কমান্ড হ্যান্ডলার"""
    help_text = (
        "❓ **সাহায্য**\n\n"
        "📌 **কমান্ড সমূহ:**\n"
        "/start - বট শুরু করুন\n"
        "/help - সাহায্য দেখুন\n\n"
        "📌 **ব্যবহার পদ্ধতি:**\n"
        "1️⃣ Facebook থেকে ভিডিওর লিংক কপি করুন\n"
        "2️⃣ এই বটে লিংকটি পেস্ট করে পাঠান\n"
        "3️⃣ HD বা SD কোয়ালিটি সিলেক্ট করুন\n"
        "4️⃣ ভিডিও আপনার কাছে চলে আসবে!\n\n"
        "⚠️ **দ্রষ্টব্য:**\n"
        "• শুধুমাত্র পাবলিক ভিডিও ডাউনলোড করা যাবে\n"
        "• প্রাইভেট ভিডিও ডাউনলোড সম্ভব নয়"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ইউজারের পাঠানো মেসেজ হ্যান্ডলার"""
    user_text = update.message.text.strip()

    # চেক করো এটা Facebook URL কিনা
    if not is_facebook_url(user_text):
        await update.message.reply_text(
            "❌ এটি একটি বৈধ Facebook লিংক নয়!\n\n"
            "✅ দয়া করে একটি Facebook ভিডিও/Reel এর লিংক পাঠান।\n"
            "যেমন: `https://www.facebook.com/reel/569975832234512`",
            parse_mode="Markdown",
        )
        return

    # Processing মেসেজ পাঠাও
    processing_msg = await update.message.reply_text(
        "⏳ ভিডিও খোঁজা হচ্ছে... দয়া করে অপেক্ষা করুন।"
    )

    # API থেকে ডাটা আনো
    data = fetch_video_data(user_text)

    if not data or data.get("error", True):
        await processing_msg.edit_text(
            "❌ ভিডিও খুঁজে পাওয়া যায়নি!\n\n"
            "সম্ভাব্য কারণ:\n"
            "• ভিডিওটি প্রাইভেট হতে পারে\n"
            "• লিংকটি ভুল হতে পারে\n"
            "• ভিডিওটি মুছে ফেলা হয়েছে"
        )
        return

    # ভিডিও তথ্য সংগ্রহ করো
    title = data.get("title", "Facebook Video")
    author = data.get("author", "Unknown")
    duration = format_duration(data.get("duration", 0))
    thumbnail = data.get("thumbnail", "")
    medias = data.get("medias", [])

    # ভিডিও ও অডিও আলাদা করো
    videos = [m for m in medias if m.get("type") == "video"]
    audios = [m for m in medias if m.get("type") == "audio"]

    if not videos:
        await processing_msg.edit_text("❌ ভিডিও ডাউনলোড লিংক পাওয়া যায়নি!")
        return

    # Context এ ডাটা সেভ করো (কলব্যাক এর জন্য)
    context.user_data["video_data"] = {
        "title": title,
        "author": author,
        "videos": videos,
        "audios": audios,
        "thumbnail": thumbnail,
    }

    # ইনলাইন কীবোর্ড তৈরি করো
    keyboard = []
    for i, video in enumerate(videos):
        quality = video.get("quality", "Unknown")
        extension = video.get("extension", "mp4")
        btn_text = f"📹 {quality} ({extension.upper()})"
        keyboard.append(
            [InlineKeyboardButton(btn_text, callback_data=f"video_{i}")]
        )

    # অডিও বাটন যোগ করো
    for i, audio in enumerate(audios):
        quality = audio.get("quality", "Audio")
        extension = audio.get("extension", "mp3")
        btn_text = f"🎵 {quality} ({extension.upper()})"
        keyboard.append(
            [InlineKeyboardButton(btn_text, callback_data=f"audio_{i}")]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)

    # তথ্য সহ রিপ্লাই দাও
    info_text = (
        f"✅ **ভিডিও পাওয়া গেছে!**\n\n"
        f"📌 **শিরোনাম:** {title}\n"
        f"👤 **লেখক:** {author}\n"
        f"⏱ **সময়কাল:** {duration}\n\n"
        f"👇 নিচে থেকে কোয়ালিটি সিলেক্ট করুন:"
    )

    # Processing মেসেজ ডিলিট করো
    await processing_msg.delete()

    # থাম্বনেইল সহ পাঠাও
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


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ইনলাইন বাটন কলব্যাক হ্যান্ডলার"""
    query = update.callback_query
    await query.answer()

    data = query.data
    video_data = context.user_data.get("video_data")

    if not video_data:
        await query.edit_message_caption(
            caption="❌ সেশন শেষ হয়ে গেছে। দয়া করে আবার লিংক পাঠান।"
        )
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
            quality = audios[index].get("quality", "Audio")
            media_type = "audio"

    if not download_url:
        await query.edit_message_caption(
            caption="❌ ডাউনলোড লিংক পাওয়া যায়নি!"
        )
        return

    # ডাউনলোড স্ট্যাটাস
    await query.edit_message_caption(
        caption=f"⬇️ **{quality}** কোয়ালিটিতে পাঠানো হচ্ছে... অপেক্ষা করুন।",
        parse_mode="Markdown",
    )

    try:
        if media_type == "video":
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=download_url,
                caption=f"✅ {video_data['title']}\n📹 কোয়ালিটি: {quality}\n\n🤖 @YourBotUsername",
                supports_streaming=True,
                read_timeout=120,
                write_timeout=120,
                connect_timeout=60,
            )
        elif media_type == "audio":
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=download_url,
                caption=f"✅ {video_data['title']}\n🎵 Audio\n\n🤖 @YourBotUsername",
                read_timeout=120,
                write_timeout=120,
                connect_timeout=60,
            )

        await query.edit_message_caption(
            caption=f"✅ **সফলভাবে পাঠানো হয়েছে!**\n\n📹 কোয়ালিটি: {quality}",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Send error: {e}")
        # যদি সরাসরি পাঠাতে না পারে, ডাউনলোড লিংক দাও
        fallback_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"⬇️ {quality} ডাউনলোড করুন", url=download_url)]]
        )
        await query.edit_message_caption(
            caption=(
                f"⚠️ ভিডিও সাইজ বড় হওয়ায় সরাসরি পাঠানো যাচ্ছে না।\n"
                f"নিচের বাটনে ক্লিক করে ডাউনলোড করুন।\n\n"
                f"📹 কোয়ালিটি: {quality}"
            ),
            reply_markup=fallback_keyboard,
            parse_mode="Markdown",
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Error হ্যান্ডলার"""
    logger.error(f"Update {update} caused error {context.error}")


# ==================== Main Function ====================

def main():
    """বট চালু করো"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN সেট করা হয়নি!")
        return

    # Flask সার্ভার আলাদা থ্রেডে চালাও (Render এর জন্য)
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"✅ Flask server started on port {PORT}")

    # Bot Application তৈরি করো
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .read_timeout(120)
        .write_timeout(120)
        .connect_timeout(60)
        .build()
    )

    # Handlers যোগ করো
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)

    # Bot চালু করো
    logger.info("✅ Bot is starting...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
