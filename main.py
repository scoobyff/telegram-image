import os
import requests
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from urllib.parse import urlparse
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Hi! Send me an image URL and I\'ll download it and send it back to you as a high-quality photo!'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """
    🤖 Image Download Bot
    
    Simply send me a direct image URL and I'll:
    1. Download the image
    2. Send it back to you as a high-quality photo
    3. Clean up the temporary file
    
    Supported formats: JPG, JPEG, PNG, GIF, BMP, WEBP
    
    Example URLs:
    https://example.com/image.jpg
    https://example.com/photo.png
    """
    await update.message.reply_text(help_text)

def is_valid_image_url(url: str) -> bool:
    """Check if URL is a valid image URL."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        
        valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
        return any(parsed.path.lower().endswith(ext) for ext in valid_extensions)
    except:
        return False

def get_image_extension(url: str, content_type: str = None) -> str:
    """Get image extension from URL or content type."""
    parsed = urlparse(url)
    path = Path(parsed.path)
    if path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        return path.suffix.lower()
    
    if content_type:
        content_type = content_type.lower()
        if 'jpeg' in content_type or 'jpg' in content_type:
            return '.jpg'
        elif 'png' in content_type:
            return '.png'
        elif 'gif' in content_type:
            return '.gif'
        elif 'bmp' in content_type:
            return '.bmp'
        elif 'webp' in content_type:
            return '.webp'
    
    return '.jpg'

async def download_and_send_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download image from URL and send it back as a photo with 100% quality."""
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ Please send a valid URL starting with http:// or https://")
        return
    
    if not is_valid_image_url(url):
        await update.message.reply_text(
            "❌ This doesn't appear to be a direct image URL. "
            "Please make sure the URL ends with an image extension (.jpg, .png, etc.)"
        )
        return
    
    processing_msg = await update.message.reply_text("⏳ Downloading image...")
    temp_file_path = None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0'
        }
        
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', '').lower()
        if not content_type.startswith('image/'):
            await processing_msg.edit_text("❌ The URL doesn't point to an image file.")
            return
        
        extension = get_image_extension(url, content_type)
        
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temp_file:
            temp_file_path = temp_file.name
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
        
        await processing_msg.edit_text("📤 Sending image as photo...")
        
        with open(temp_file_path, 'rb') as photo_file:
            await update.message.reply_photo(photo=photo_file)
        
        await processing_msg.delete()
        
    except requests.exceptions.Timeout:
        await processing_msg.edit_text("❌ Download timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        await processing_msg.edit_text(f"❌ Error downloading image: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        await processing_msg.edit_text("❌ An unexpected error occurred while processing the image.")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f"Temporary file {temp_file_path} deleted successfully")
            except Exception as e:
                logger.error(f"Error deleting temporary file {temp_file_path}: {e}")

def main() -> None:
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send_image))
        print("Bot is starting...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Failed to start the bot: {e}")

if __name__ == '__main__':
    main()