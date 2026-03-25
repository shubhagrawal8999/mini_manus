"""
Telegram command and message handlers.

BUG FIXED:
  safe_reply previously called html.escape() on the bot's own response while
  parse_mode was HTML — this corrupted every <b>/<i>/<code> tag, turning them
  into literal &lt;b&gt; text on screen.  The fix: only escape raw *user input*
  when echoing it back; trust the orchestrator's own output.
"""

import html
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.agent.orchestrator import orchestrator
from bot.agent.memory import memory
from bot.config import Settings


# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────
async def safe_reply(update: Update, text: str, parse_mode=ParseMode.HTML):
    """
    Send a message, splitting if over Telegram's 4 096-char limit.

    DO NOT html.escape() here — the bot's own formatted strings already
    contain intentional HTML tags.  Escaping them would break rendering.
    Only escape *user-supplied* text before embedding it inside an HTML
    template (e.g. f"Hello {html.escape(user.first_name)}").
    """
    if not text:
        text = "⚠️ No response was generated."

    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i : i + 4000], parse_mode=parse_mode)
    else:
        await update.message.reply_text(text, parse_mode=parse_mode)


# ──────────────────────────────────────────────
# /start
# ──────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome = (
        f"🤖 <b>Mini-Manus AI Agent</b> Activated!\n\n"
        f"Hello <b>{html.escape(user.first_name)}</b>!\n\n"
        "I can help you automate:\n"
        "📧 <b>Email</b> — <i>Send cold outreach to john@company.com</i>\n"
        "💬 <b>WhatsApp</b> — <i>Message +91xxxxxxxxxx: meeting confirmed</i>\n"
        "🔍 <b>Research</b> — <i>Research top AI agent frameworks</i>\n"
        "💼 <b>LinkedIn</b> — <i>Post an update about my new project</i>\n"
        "⏰ <b>Schedule</b> — <i>Remind me every Friday to post on LinkedIn</i>\n\n"
        "Just tell me what you need in plain English!\n\n"
        "Type /help for examples · /status for usage stats."
    )
    await safe_reply(update, welcome)


# ──────────────────────────────────────────────
# /help
# ──────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "<b>Example Commands:</b>\n\n"
        "1️⃣ <b>Email:</b>\n"
        "<i>Send email to contact@startup.com subject 'Partnership' "
        "body 'Would love to collaborate'</i>\n\n"
        "2️⃣ <b>WhatsApp:</b>\n"
        "<i>WhatsApp +91-9876543210: Project delivered on time</i>\n\n"
        "3️⃣ <b>Research:</b>\n"
        "<i>Research top 5 CRM tools and their pricing</i>\n\n"
        "4️⃣ <b>LinkedIn Post:</b>\n"
        "<i>Post on LinkedIn: Excited to share my new AI project!</i>\n\n"
        "5️⃣ <b>Schedule:</b>\n"
        "<i>Every Thursday at 9am remind me to check LinkedIn messages</i>\n\n"
        "6️⃣ <b>Complex chain:</b>\n"
        "<i>Research top 3 VCs in India, draft an intro email to each, "
        "schedule follow-ups in 3 days</i>\n\n"
        "I understand natural language — just describe what you want!"
    )
    await safe_reply(update, help_text)


# ──────────────────────────────────────────────
# /status
# ──────────────────────────────────────────────
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        stats = await memory.get_stats(user_id)
        tools_str = ", ".join(stats["recent_tools"]) if stats["recent_tools"] else "None yet"
        text = (
            f"📊 <b>Your Usage</b>\n\n"
            f"🗣️ Total interactions: <b>{stats['total_interactions']}</b>\n"
            f"💰 Total cost: <b>${stats['total_cost_usd']:.4f} USD</b>\n"
            f"🛠️ Recent tools: <b>{html.escape(tools_str)}</b>\n\n"
            "🟢 Bot status: Online\n"
            "💾 Memory: Persistent (SQLite)\n"
            "🧠 Models: DeepSeek primary · OpenAI fallback"
        )
        await safe_reply(update, text)
    except Exception as e:
        await safe_reply(update, f"❌ Error fetching stats: {html.escape(str(e))}")


# ──────────────────────────────────────────────
# Main message handler
# ──────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all plain text through the ReAct orchestrator."""
    user_id = update.effective_user.id
    message_text = update.message.text

    await update.message.chat.send_action(action="typing")
    lower_text = (message_text or "").lower()
    likely_long_task = any(
        kw in lower_text
        for kw in [
            "research",
            "search",
            "linkedin",
            "email",
            "schedule",
            "whatsapp",
            "post",
            "send",
        ]
    )
    if likely_long_task:
        await safe_reply(
            update,
            "⏳ I am working on your request. This may take 2 to 3 minutes.",
        )

    try:
        result = await orchestrator.process(user_id, message_text)
        response = result["response"] or "⚠️ Agent returned an empty response."

        # Append cost footer for admin or costly calls
        if user_id == Settings.ADMIN_USER_ID or result["cost_usd"] > 0.01:
            response += (
                f"\n\n<i>💸 ${result['cost_usd']:.4f} · "
                f"⏱ {result['execution_time_ms']}ms · "
                f"🤖 {html.escape(result['model'])}</i>"
            )

        await safe_reply(update, response)

    except Exception as e:
        import traceback
        print(f"[ERROR] user={user_id}\n{traceback.format_exc()}")

        await safe_reply(
            update,
            "❌ Something went wrong. The error has been logged. Please try again.",
        )

        if Settings.ADMIN_USER_ID and context.bot:
            try:
                await context.bot.send_message(
                    chat_id=Settings.ADMIN_USER_ID,
                    text=(
                        f"🚨 Error · user {user_id}\n"
                        f"Msg: {html.escape(message_text[:200])}\n"
                        f"Err: {html.escape(str(e))}"
                    ),
                )
            except Exception:
                pass
