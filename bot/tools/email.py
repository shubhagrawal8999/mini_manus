"""
Email automation using yagmail.
Requires GMAIL_USER and GMAIL_APP_PASSWORD in env.

BUG FIXED:
  yagmail.send() is a blocking synchronous SMTP call.  Calling it directly
  inside `async def execute()` froze the entire bot event loop until the
  SMTP transaction completed (or timed out).
  Fix: wrapped in asyncio.to_thread() so it runs in a thread pool without
  blocking other Telegram updates.

SETUP CHECKLIST (Gmail):
  1. Enable 2-Step Verification on your Google account.
  2. Go to Google Account → Security → App Passwords.
  3. Generate a password for "Mail" / "Other".
  4. Put that 16-char password in GMAIL_APP_PASSWORD (no spaces).
  5. GMAIL_USER should be your full address, e.g. you@gmail.com
"""

import asyncio
from typing import Literal

import yagmail

from bot.config import Settings
from bot.tools.base import Tool, ToolResult


class EmailTool(Tool):
    name = "send_email"
    description = (
        "Send an email via Gmail. Use for outreach, notifications, and follow-ups. "
        "Requires GMAIL_USER and GMAIL_APP_PASSWORD to be configured."
    )

    parameters = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line",
            },
            "body": {
                "type": "string",
                "description": "Email body content (plain text or basic HTML)",
            },
            "template": {
                "type": "string",
                "enum": ["cold_outreach", "follow_up", "meeting_request", "none"],
                "description": "Optional template to wrap the body with",
            },
        },
        "required": ["to", "subject", "body"],
    }

    def __init__(self):
        self._yag: yagmail.SMTP | None = None
        self._setup_error: str = ""

        if Settings.GMAIL_USER and Settings.GMAIL_APP_PASSWORD:
            try:
                # yagmail.SMTP() just stores credentials; it doesn't open a
                # connection here, so this is safe to call synchronously.
                self._yag = yagmail.SMTP(
                    user=Settings.GMAIL_USER,
                    password=Settings.GMAIL_APP_PASSWORD,
                )
            except Exception as exc:
                self._setup_error = str(exc)
                print(f"[EmailTool] Setup failed: {exc}")
        else:
            self._setup_error = "GMAIL_USER or GMAIL_APP_PASSWORD not set in environment."

    # ------------------------------------------------------------------
    # Template helpers
    # ------------------------------------------------------------------
    def _apply_template(
        self,
        body: str,
        template: str,
        sender: str,
    ) -> str:
        if template == "cold_outreach":
            return (
                f"Hi there,\n\n"
                f"I came across your profile and was impressed by your work.\n\n"
                f"{body}\n\n"
                f"Would you be open to a brief conversation next week?\n\n"
                f"Best regards,\n{sender}"
            )
        if template == "follow_up":
            return (
                f"Hi,\n\n"
                f"Just following up on my previous message.\n\n"
                f"{body}\n\n"
                f"Looking forward to hearing from you.\n\n"
                f"Best,\n{sender}"
            )
        if template == "meeting_request":
            return (
                f"Hi,\n\n"
                f"I'd like to schedule a meeting to discuss:\n\n"
                f"{body}\n\n"
                f"Please let me know your availability.\n\n"
                f"Best,\n{sender}"
            )
        return body  # "none" or unknown template — use body as-is

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------
    async def execute(
        self,
        to: str,
        subject: str,
        body: str,
        template: Literal["cold_outreach", "follow_up", "meeting_request", "none"] = "none",
    ) -> ToolResult:

        if not self._yag:
            return ToolResult(
                status="error",
                message=f"Email not configured: {self._setup_error}",
                error=self._setup_error,
                retryable=False,
            )

        final_body = self._apply_template(body, template, Settings.GMAIL_USER)

        def _send_blocking():
            """Runs in a thread pool — keeps event loop free."""
            self._yag.send(to=to, subject=subject, contents=final_body)

        try:
            # KEY FIX: run the blocking SMTP call in a thread pool
            await asyncio.to_thread(_send_blocking)

            return ToolResult(
                status="success",
                message=f"✅ Email sent to {to}",
                data={"recipient": to, "subject": subject},
            )

        except Exception as exc:
            return ToolResult(
                status="error",
                message=f"Failed to send email: {exc}",
                error=str(exc),
                retryable=True,
            )
