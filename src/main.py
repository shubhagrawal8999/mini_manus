from fastapi import FastAPI, Request, Response
from src.config import Config
from src.memory import MemoryManager
from src.router import IntentRouter
from src.executor import ActionExecutor
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import json

app = FastAPI()
memory = MemoryManager()
router = IntentRouter(memory)
executor = ActionExecutor(memory)

# Telegram bot instance (lazy init)
bot_app = None

@app.on_event("startup")
async def startup():
    await memory.init_db()
    global bot_app
    bot_app = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    await bot_app.initialize()
    # Register commands
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("help", help_command))
    # Message handler
    from telegram.ext import MessageHandler, filters
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("AI Agent with memory ready. Send me a task like 'post on LinkedIn ...'")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I can post to LinkedIn, send email, deep search, take snapshots. I learn from mistakes.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text
    intent, params = await router.route(text, user_id)
    result_msg = await executor.execute_with_repair(intent, params, user_id)
    await update.message.reply_text(result_msg)

@app.post("/webhook")
async def webhook(request: Request):
    global bot_app
    if not bot_app:
        return Response(status_code=500)
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return Response(status_code=200)

@app.get("/health")
async def health():
    return {"status": "ok"}

# For local testing with polling (not used on Railway)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
