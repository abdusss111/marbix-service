import os
import httpx
import logging
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_GROUP_ID")


def send_to_telegram(email: str, name: str, number: str, date: str):
    """Send notification to Telegram about new pro plan request"""
    try:
        if not BOT_TOKEN or not CHAT_ID:
            logger.warning("Telegram bot token or chat ID not configured")
            return False
            
        text = f"📝 New submission\nName: {name}\nEmail: {email}\nNumber: {number}\nDate: {date}"
        
        response = httpx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text}
        )
        
        if response.status_code == 200:
            logger.info(f"Telegram notification sent successfully for {email}")
            return True
        else:
            logger.error(f"Failed to send Telegram notification: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending Telegram notification: {str(e)}")
        return False
