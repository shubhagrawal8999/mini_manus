"""
Email automation via Gmail SMTP.
Requires GMAIL_USER and GMAIL_APP_PASSWORD in env.

WHY THIS VERSION:
  Some deployments fail with yagmail/keyring backend issues in headless
  containers. This implementation uses Python's built-in SMTP stack
  directly, making behavior predictable across local + Railway/Docker.
"""

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Literal

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
        self._setup_error: str = ""
        if not (Settings.GMAIL_USER and Settings.GMAIL_APP_PASSWORD):
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

        if self._setup_error:
            return ToolResult(
                status="error",
                message=f"Email not configured: {self._setup_error}",
                error=self._setup_error,
                retryable=False,
            )

        final_body = self._apply_template(body, template, Settings.GMAIL_USER)

        def _send_blocking():
            """Runs in a thread pool — keeps event loop free."""
            msg = EmailMessage()
            msg["From"] = Settings.GMAIL_USER
            msg["To"] = to
            msg["Subject"] = subject
            msg.set_content(final_body)

            with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(Settings.GMAIL_USER, Settings.GMAIL_APP_PASSWORD)
                smtp.send_message(msg)

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
