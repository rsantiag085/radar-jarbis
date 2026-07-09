import os
import sys
import asyncio
import io
import re
import html
import urllib.request
from pathlib import Path
import httpx
from telegram import Bot
from telegram.constants import ParseMode

# Ensure the root dir is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import settings
from src.converters import process_async

def scrape_telegram_message(url):
    print(f"📡 Scraping Telegram message: {url}...")
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    with urllib.request.urlopen(req) as response:
        html_content = response.read().decode('utf-8')
    
    og_desc = re.search(r'<meta property="og:description" content="([^"]+)"', html_content)
    og_image = re.search(r'<meta property="og:image" content="([^"]+)"', html_content)
    
    text = html.unescape(og_desc.group(1)) if og_desc else ""
    image_url = html.unescape(og_image.group(1)) if og_image else None
    
    return text, image_url

async def main():
    if len(sys.argv) < 2:
        print("Usage: python scratch/process_and_send.py <TELEGRAM_MESSAGE_URL>")
        sys.exit(1)
        
    url = sys.argv[1]
    
    try:
        text, image_url = scrape_telegram_message(url)
    except Exception as e:
        print(f"❌ Error scraping Telegram message: {e}")
        sys.exit(1)
        
    if not text:
        print("❌ Error: No description found in the Telegram message!")
        sys.exit(1)
        
    print("⏳ Processing the message text...")
    formatted_text = await process_async(text)
    if not formatted_text:
        print("❌ Error: No Amazon link processed/converted!")
        sys.exit(1)

    print("✨ Formatted message content:")
    print("-" * 50)
    print(formatted_text)
    print("-" * 50)

    photo_bytes = None
    if image_url:
        print(f"⏳ Fetching image bytes from {image_url}...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(image_url)
                r.raise_for_status()
                photo_bytes = r.content
            print(f"✅ Image fetched successfully ({len(photo_bytes)} bytes)")
        except Exception as e:
            print(f"⚠️ Failed to fetch image: {e}")
            photo_bytes = None

    print(f"🚀 Sending to output channel: {settings.OUTPUT_CHANNEL_ID}...")
    try:
        async with Bot(token=settings.TELEGRAM_BOT_TOKEN) as bot:
            if photo_bytes and len(formatted_text) <= 1024:
                await bot.send_photo(
                    chat_id=settings.OUTPUT_CHANNEL_ID,
                    photo=io.BytesIO(photo_bytes),
                    caption=formatted_text,
                    parse_mode=ParseMode.HTML,
                )
            else:
                if photo_bytes:
                    await bot.send_photo(
                        chat_id=settings.OUTPUT_CHANNEL_ID,
                        photo=io.BytesIO(photo_bytes),
                    )
                await bot.send_message(
                    chat_id=settings.OUTPUT_CHANNEL_ID,
                    text=formatted_text,
                    parse_mode=ParseMode.HTML,
                )
            print("🎉 Sent successfully!")
    except Exception as e:
        print(f"❌ Error sending message: {e}")

if __name__ == "__main__":
    asyncio.run(main())
