"""
Telegram command and message handlers.
All async, non-blocking, with error handling.
"""

import html
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from bot.agent.orchestrator import orchestrator
from bot.agent.memory import memory
from bot.config import Settings

# Helper: Safe message sender
async def safe_reply(update: Update, text: str, parse_mode=ParseMode.HTML):
    """Send message with length and parse safety."""
    if not text:
        text = "No response generated."
    
    # Escape HTML if using HTML mode
    if parse_mode == ParseMode.HTML:
        text = html.escape(text)
    
    # Telegram limit is 4096, we use 4000 for safety
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode=parse_mode)
    else:
        await update.message.reply_text(text, parse_mode=parse_mode)

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message."""
    user = update.effective_user
    
    welcome = f"""🤖 <b>Mini-Manus AI Agent</b> Activated!

Hello {html.escape(user.first_name)}!

I can help you automate:
📧 <b>Emails</b> - "Send cold outreach to john@company.com"
💬 <b>WhatsApp</b> - "Message +91xxxxxxxxxx meeting confirmed"
🔍 <b>Research</b> - "Research AI agent frameworks"
⏰ <b>Scheduling</b> - "Remind me every Friday to post on LinkedIn"

Just tell me what you need in natural language!

Type /help for examples or /status to see your usage."""
    
    await safe_reply(update, welcome)

# Command: /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help with examples."""
    help_text = """<b>Example Commands:</b>

1️⃣ <b>Email:</b>
"Send email to contact@startup.com subject 'Partnership' body 'Would love to collaborate on AI projects'"

2️⃣ <b>WhatsApp:</b>
"WhatsApp +91-9876543210: Project delivered on time"

3️⃣ <b>Research:</b>
"Research top 5 CRM tools and their pricing"

4️⃣ <b>Schedule:</b>
"Every Thursday at 9am remind me to check LinkedIn messages"

5️⃣ <b>Complex:</b>
"Find email of Tesla HR, send my resume, schedule follow-up in 3 days"

I understand natural language - just describe what you want!"""
    
    await safe_reply(update, help_text)

# Command: /status
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user stats."""
    user_id = update.effective_user.id
    
    try:
        stats = await memory.get_stats(user_id)
        
        status_text = f"""📊 <b>Your Usage</b>

🗣️ Total Interactions: {stats['total_interactions']}
💰 Total Cost: ${stats['total_cost_usd']:.4f} USD
🛠️ Recent Tools: {', '.join(stats['recent_tools']) if stats['recent_tools'] else 'None yet'}

🟢 Bot Status: Online
💾 Memory: Persistent (SQLite)
🧠 Models: DeepSeek + OpenAI fallback"""
        
        await safe_reply(update, status_text)
        
    except Exception as e:
        await safe_reply(update, f"Error fetching stats: {str(e)}")

# Main message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process all non-command text messages."""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Show typing indicator
    await update.message.chat.send_action(action="typing")
    
    try:
        # Process through orchestrator
        result = await orchestrator.process(user_id, message_text)
        
        # Format response with metadata (optional, for transparency)
        response = result["response"]
        
        # Add cost info for admin or if cost > $0.01
        if user_id == Settings.ADMIN_USER_ID or result["cost_usd"] > 0.01:
            footer = f"\n\n<i>Cost: ${result['cost_usd']:.4f} | Time: {result['execution_time_ms']}ms | Model: {result['model']}</i>"
            response += footer
        
        await safe_reply(update, response, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        # Log error
        print(f"Error processing message from {user_id}: {e}")
        
        # User-friendly error
        await safe_reply(
            update, 
            "❌ Sorry, something went wrong processing your request. Error has been logged. Please try again or contact admin.",
            parse_mode=ParseMode.HTML
        )
        
        # Notify admin if configured
        if Settings.ADMIN_USER_ID and context.bot:
            try:
                await context.bot.send_message(
                    chat_id=Settings.ADMIN_USER_ID,
                    text=f"🚨 Error for user {user_id}:\nMessage: {html.escape(message_text[:100])}...\nError: {html.escape(str(e))}"
                )
            except:
                pass
