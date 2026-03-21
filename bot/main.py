"""
Main entry point for the bot.
Initializes all components and starts polling.
"""

import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.config import Settings, router
from bot.agent.memory import memory
from bot.telegram.handlers import start, help_command, status, handle_message
from bot.telegram.error_handler import error_handler

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    """Called after bot initialization."""
    # Validate settings
    missing = Settings.validate()
    if missing:
        logger.error(f"Missing required settings: {missing}")
        raise ValueError(f"Missing: {', '.join(missing)}")
    
    # Initialize database
    await memory._init_db()
    logger.info("Database initialized")
    
    # Notify admin that bot is up
    if Settings.ADMIN_USER_ID:
        try:
            await application.bot.send_message(
                chat_id=Settings.ADMIN_USER_ID,
                text="🟢 <b>Mini-Manus Bot Started</b>\n\nBot is online and ready to accept commands.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not notify admin: {e}")
    
    logger.info("Bot initialized successfully")

async def post_shutdown(application: Application):
    """Called on shutdown."""
    # Close API connections
    await router.close()
    logger.info("Shutdown complete")

def main():
    """Start the bot."""
    
    # Validate before starting
    missing = Settings.validate()
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in your values.")
        return
    
    # Create application
    application = (
        Application.builder()
        .token(Settings.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)  # Handle multiple users simultaneously
        .build()
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start polling
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
