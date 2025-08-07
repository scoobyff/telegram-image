import os
import requests
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from urllib.parse import urlparse
import tempfile
from pathlib import Path

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token - Replace with your actual token from @BotFather
BOT_TOKEN = "7930306003:AAGjq3KMGfJiSsA5N3irttWYHHvuS2plQXM"

# Fallback to environment variable if token not set in code
if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE_REPLACE_THIS":
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        logger.error("Please set your bot token either in code or environment variable!")
        exit(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        '🤖 **Image Download Bot**\n\n'
        'Hi! Send me an image URL and I\'ll download it and send it back to you as a high-quality photo!\n\n'
        '✨ **Features:**\n'
        '• Downloads from any public image URL\n'
        '• Maintains original quality\n'
        '• Supports all common formats\n'
        '• Fast and reliable\n\n'
        'Just paste any image URL to get started!',
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """
🤖 **Image Download Bot - Help**

**How to use:**
1. Find any image URL on the internet
2. Send me the complete URL
3. I'll download and send it back to you!

**Supported formats:** 
JPG, JPEG, PNG, GIF, BMP, WEBP

**Example URLs:**
```
https://example.com/image.jpg
https://cdn.example.com/photo.png
https://images.example.com/picture.gif
```

**Tips:**
• Make sure the URL ends with an image extension
• The image must be publicly accessible
• Maximum file size: 20MB (Telegram limit)
• Some websites may block automated downloads

**Commands:**
/start - Welcome message
/help - Show this help message

**Having issues?** Make sure your URL is a direct link to an image file!
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

def is_valid_image_url(url: str) -> bool:
    """Check if URL is a valid image URL."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        
        # Check if URL ends with common image extensions
        valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
        path_lower = parsed.path.lower()
        
        # More flexible checking
        return (any(path_lower.endswith(ext) for ext in valid_extensions) or
                any(ext in url.lower() for ext in valid_extensions) or
                any(keyword in path_lower for keyword in ['image', 'img', 'photo', 'pic']))
    except:
        return False

def get_image_extension(url: str, content_type: str = None) -> str:
    """Get image extension from URL or content type."""
    # Try to get extension from URL first
    parsed = urlparse(url)
    path = Path(parsed.path.split('?')[0])  # Remove query parameters
    if path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        return path.suffix.lower()
    
    # Try to get extension from content type
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
    
    # Default to .jpg if we can't determine
    return '.jpg'

async def download_and_send_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download image from URL and send it back as a photo."""
    url = update.message.text.strip()
    
    # Check if it's a valid URL
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ Please send a valid URL starting with `http://` or `https://`\n\n"
            "Example: `https://example.com/image.jpg`",
            parse_mode='Markdown'
        )
        return
    
    # Check if it looks like an image URL
    if not is_valid_image_url(url):
        await update.message.reply_text(
            "❌ This doesn't appear to be a direct image URL.\n\n"
            "Please make sure:\n"
            "• The URL ends with an image extension (.jpg, .png, etc.)\n"
            "• Or contains image-related keywords\n"
            "• The link points directly to an image file\n\n"
            "Example: `https://example.com/photo.jpg`",
            parse_mode='Markdown'
        )
        return
    
    # Send "processing" message
    processing_msg = await update.message.reply_text("⏳ **Starting download...**", parse_mode='Markdown')
    
    temp_file_path = None
    try:
        # Enhanced headers to bypass basic bot detection
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
            'Cache-Control': 'no-cache',
            'Referer': urlparse(url).scheme + '://' + urlparse(url).netloc
        }
        
        await processing_msg.edit_text("⏳ **Downloading image...**", parse_mode='Markdown')
        
        # Make the request
        response = requests.get(url, headers=headers, timeout=30, stream=True, allow_redirects=True)
        response.raise_for_status()
        
        # Check content length
        content_length = response.headers.get('content-length')
        if content_length:
            size_mb = int(content_length) / (1024 * 1024)
            if size_mb > 20:
                await processing_msg.edit_text(
                    f"❌ **Image too large:** {size_mb:.1f}MB\n\n"
                    "Telegram photos must be under 20MB.",
                    parse_mode='Markdown'
                )
                return
        
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        if content_type and not content_type.startswith('image/'):
            await processing_msg.edit_text(
                "❌ **Not an image file**\n\n"
                f"Server returned: `{content_type}`\n"
                "Please check if the URL points directly to an image.",
                parse_mode='Markdown'
            )
            return
        
        # Get file extension
        extension = get_image_extension(url, content_type)
        
        await processing_msg.edit_text("⏳ **Processing image data...**", parse_mode='Markdown')
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temp_file:
            temp_file_path = temp_file.name
            
            # Download with size checking
            total_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
                    total_size += len(chunk)
                    
                    # Check size limit during download
                    if total_size > 20 * 1024 * 1024:  # 20MB
                        await processing_msg.edit_text(
                            "❌ **Download stopped** - File too large (>20MB)",
                            parse_mode='Markdown'
                        )
                        return
        
        # Verify file was downloaded
        if not os.path.exists(temp_file_path) or os.path.getsize(temp_file_path) == 0:
            await processing_msg.edit_text("❌ **Download failed** - File is empty or corrupted.")
            return
        
        await processing_msg.edit_text("📤 **Sending image...**", parse_mode='Markdown')
        
        # Send the image
        with open(temp_file_path, 'rb') as photo_file:
            file_size = os.path.getsize(temp_file_path)
            size_mb = file_size / (1024 * 1024)
            
            # Create caption
            caption = f"✅ **Download complete!**\n📁 Size: {size_mb:.2f} MB"
            
            await update.message.reply_photo(
                photo=photo_file,
                caption=caption,
                parse_mode='Markdown'
            )
        
        # Delete processing message
        await processing_msg.delete()
        
    except requests.exceptions.Timeout:
        await processing_msg.edit_text(
            "❌ **Download timed out**\n\n"
            "The server is taking too long to respond.",
            parse_mode='Markdown'
        )
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else "Unknown"
        await processing_msg.edit_text(
            f"❌ **HTTP Error {status_code}**\n\n"
            "The server couldn't provide the image.",
            parse_mode='Markdown'
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        await processing_msg.edit_text(
            "❌ **Network error**\n\n"
            "Could not download the image. Please try again.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await processing_msg.edit_text(
            "❌ **An unexpected error occurred**",
            parse_mode='Markdown'
        )
    
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f"Temporary file deleted: {temp_file_path}")
            except Exception as e:
                logger.error(f"Error deleting temp file: {e}")

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send_image))
    
    # Get port from environment (Render provides this)
    port = int(os.getenv('PORT', 8080))
    
    print(f"🤖 Telegram Image Bot starting on port {port}...")
    print("✅ Bot is ready to download images!")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()