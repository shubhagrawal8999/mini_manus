"""
Email automation using yagmail.
Requires GMAIL_USER and GMAIL_APP_PASSWORD in env.
"""

import yagmail
from typing import Dict, Any, Literal
from bot.config import Settings
from bot.tools.base import Tool, ToolResult

class EmailTool(Tool):
    """Send emails via Gmail."""
    
    name = "send_email"
    description = "Send email via Gmail. Use for outreach, notifications, follow-ups."
    
    parameters = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address"
            },
            "subject": {
                "type": "string",
                "description": "Email subject line"
            },
            "body": {
                "type": "string",
                "description": "Email body content"
            },
            "template": {
                "type": "string",
                "enum": ["cold_outreach", "follow_up", "meeting_request", "none"],
                "description": "Optional template to use"
            }
        },
        "required": ["to", "subject", "body"]
    }
    
    def __init__(self):
        self.yag = None
        if Settings.GMAIL_USER and Settings.GMAIL_APP_PASSWORD:
            try:
                self.yag = yagmail.SMTP(Settings.GMAIL_USER, Settings.GMAIL_APP_PASSWORD)
            except Exception as e:
                print(f"Email setup failed: {e}")
    
    async def execute(
        self,
        to: str,
        subject: str,
        body: str,
        template: Literal["cold_outreach", "follow_up", "meeting_request", "none"] = "none"
    ) -> ToolResult:
        if not self.yag:
            return ToolResult(
                status="error",
                message="Email not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD.",
                error="Configuration missing",
                retryable=False
            )
        
        # Apply templates
        if template == "cold_outreach":
            body = f"""Hi there,

I came across your profile and was impressed by your work in the industry.

{body}

Would you be open to a brief conversation next week?

Best regards,
{Settings.GMAIL_USER}
"""
        elif template == "follow_up":
            body = f"""Hi,

Just following up on my previous message.

{body}

Looking forward to hearing from you.

Best,
{Settings.GMAIL_USER}
"""
        elif template == "meeting_request":
            body = f"""Hi,

I'd like to schedule a meeting to discuss:

{body}

Please let me know your availability.

Best,
{Settings.GMAIL_USER}
"""
        
        try:
            self.yag.send(to=to, subject=subject, contents=body)
            return ToolResult(
                status="success",
                message=f"Email sent to {to}",
                data={"recipient": to, "subject": subject}
            )
        except Exception as e:
            return ToolResult(
                status="error",
                message=f"Failed to send email: {str(e)}",
                error=str(e),
                retryable=True  # Can retry with different params
            )
