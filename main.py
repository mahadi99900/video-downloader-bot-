import logging
import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode
import yt_dlp

# --- Web Server Setup (to keep Render happy) ---
app = Flask(__name__)

@app.route('/')
def hello_world():
    return "I'm alive!"

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
# --- End of Web Server Setup ---


# --- Bot Code ---
# Setting up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Your Telegram Bot Token
BOT_TOKEN = "8312197624:AAGc8e8rdTbzPG1ar0Z7s4usOqDcUWXQjHU" # আপনার বট টোকেন

# A set to track users who are currently downloading
DOWNLOADING_USERS = set()

# Function for the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        f"👋 Hi {user.mention_html()}!\n\nI am a powerful video downloader bot. Send /help to see the usage instructions.",
    )

# Function for the /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
*Video Downloader Bot - Instructions*

I can download videos from most supported websites. Please follow the rules below.
---
*✅ Main Command:*
`/dl <video_link>`

*Usage:* Type `/dl`, followed by a space, and then your video link.

*Note:* Each user can download one video at a time.
---
*📄 Examples:*

*Social Media:*
`/dl https://www.youtube.com/watch?v=video_id`
`/dl https://www.facebook.com/share/v/link_id/`

*Other Websites:*
The same `/dl` command works for hundreds of sites.
`/dl https://www.xvideos.com/video12345/video_title`
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# Main function to download videos
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    message = update.message
    
    if user_id in DOWNLOADING_USERS:
        await message.reply_text("You already have a download in progress. Please wait until it's finished.")
        return

    if not context.args:
        await message.reply_text("Usage: /dl <video_link>")
        return
        
    url = context.args[0]
    DOWNLOADING_USERS.add(user_id)
    
    reply_msg = await message.reply_text(
        "📥 Starting download, please wait...",
        reply_to_message_id=message.message_id
    )

    filename = None
    try:
        ydl_opts = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': '%(id)s.%(ext)s',
            'noplaylist': True, 
            'age_limit': 18,
            'socket_timeout': 120,  # Increased timeout for larger files
            'logger': logger,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)

        await reply_msg.edit_text(f"✅ Download complete! Now sending the video to you...")
        
        video_title = info_dict.get('title', 'Downloaded Video')
        video_height = info_dict.get('height')
        final_caption = f"{video_title}\n\nResolution: {video_height}p" if video_height else video_title

        # Send the video
        await context.bot.send_video(
            chat_id=update.effective_chat.id, 
            video=open(filename, 'rb'),
            caption=final_caption, 
            reply_to_message_id=message.message_id,
            supports_streaming=True
        )
        
        # Delete the status message and the local file after successful upload
        await reply_msg.delete()
        if filename and os.path.exists(filename):
            os.remove(filename)

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp error for {url}: {e}")
        error_message = str(e).split(':')[-1].strip()
        await reply_msg.edit_text(f"❌ Sorry, failed to download.\n\n*Reason:* `{error_message}`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"General error for {url}: {e}")
        await reply_msg.edit_text(f"❌ An unexpected error occurred.\n\n*Error:* `{str(e)}`", parse_mode=ParseMode.MARKDOWN)
    finally:
        # Always remove the user from the downloading set, whether it fails or succeeds
        DOWNLOADING_USERS.remove(user_id)
        # Clean up file just in case it was left over from a failed send
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except OSError as e:
                logger.error(f"Error removing file {filename}: {e}")


def run_bot() -> None:
    """Function to start and run the bot"""
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30).read_timeout(30)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("dl", download_video))
    logger.info("Bot has started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

# --- Main execution block ---
if __name__ == '__main__':
    # Run the Flask web server in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    # Run the Bot in the main thread
    run_bot()