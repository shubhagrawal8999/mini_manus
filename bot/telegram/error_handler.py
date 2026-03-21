"""
Global error handling for Telegram bot.
Catches all unhandled exceptions, logs them, notifies admin.
"""

import html
import traceback
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from bot.config import Settings

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all errors."""
    
    # Get error details
    error = context.error
    error_traceback = ''.join(traceback.format_exception(None, error, error.__traceback__))
    
    # Log to console
    print(f"Exception while handling update {update}:\n{error_traceback}")
    
    # Notify admin
    if Settings.ADMIN_USER_ID and context.bot:
        try:
            # Truncate if too long
            tb_text = error_traceback[-4000:] if len(error_traceback) > 4000 else error_traceback
            
            message = (
                f"🚨 <b>Bot Error</b>\n\n"
                f"<b>Error:</b> {html.escape(str(error))}\n"
                f"<b>User:</b> {update.effective_user.id if update and update.effective_user else 'Unknown'}\n"
                f"<b>Update:</b> {update.to_dict() if update else 'None'}\n\n"
                f"<pre>{html.escape(tb_text)}</pre>"
            )
            
            await context.bot.send_message(
                chat_id=Settings.ADMIN_USER_ID,
                text=message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Failed to notify admin: {e}")
    
    # Notify user if possible
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ An error occurred while processing your request. The admin has been notified.",
                parse_mode=ParseMode.HTML
            )
        except:
            pass  # Ignore if we can't reply
