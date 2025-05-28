import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file if it exists
load_dotenv()

# Bot token from environment variable or fallback
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8184215515:AAEVINsnkj_fTBbxZfBpvqZtUCsNj2kvwjo")

# List of admin Telegram user IDs
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "1477944238")
ADMINS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(",") if admin_id.strip().isdigit()]

# Admin channel and feedback channel
ADMIN_CHANNEL = os.environ.get("ADMIN_CHANNEL", "englishpodcasts_panorama")
FEEDBACK_CHANNEL = os.environ.get("FEEDBACK_CHANNEL", "usercommentss")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "masterquizz_bot")

# Database filename
DATABASE_FILE = os.environ.get("DATABASE_FILE", "bot_users.db")

# Rate limiting settings
RATE_LIMIT = {
    "default": {  # Default rate limit for regular users
        "requests": 30,  # Number of requests
        "per_seconds": 60,  # Time window in seconds
    },
    "admin": {  # Rate limit for admin users (higher limits)
        "requests": 100,
        "per_seconds": 60,
    }
}

# Performance settings
MAX_CONCURRENT_PROCESSES = int(os.environ.get("MAX_CONCURRENT_PROCESSES", "10"))
MAX_QUESTIONS_PER_TEST = int(os.environ.get("MAX_QUESTIONS_PER_TEST", "100"))
AI_EXTRACTION_TIMEOUT = int(os.environ.get("AI_EXTRACTION_TIMEOUT", "30"))  # seconds

# Logging configuration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Convert string log level to logging constant
def get_log_level(level_name):
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    return levels.get(level_name.upper(), logging.INFO)

# Path to manual video
MANUAL_VIDEO_PATH = "manual.mp4"

# Message texts
WELCOME_MESSAGE = "Welcome to our bot! Use /help to see available commands."
HELP_MESSAGE = """
Available commands:
/start - Start the bot
/help - Show this help message
/guide - Show guide with video tutorial
/admin - Access admin panel (for admins only)
"""
GUIDE_TEXT = """
Here's a detailed guide on how to use this bot:

1. Use the /start command to begin interacting with the bot.
2. Navigate through the menu to access different features.
3. If you have any questions, use the /help command.

Check out the video tutorial below for a visual guide:
"""
ADMIN_PANEL_MESSAGE = """
Admin Panel

You can manage the bot from here. Select an option:
"""
BROADCAST_START_MESSAGE = """
Broadcast mode activated. You can send a message to all users.

Send the content you want to broadcast (text, photo, video, or poll).
Or use /cancel to cancel the broadcast.
"""
BROADCAST_CONFIRM_MESSAGE = """
Are you sure you want to send this message to all users?
"""
