# bot/tools/whatsapp.py — minimal correct stub
from bot.tools.base import Tool, ToolResult
from typing import Literal, Optional

class WhatsAppTool(Tool):
    name = "send_whatsapp"
    description = "Send a WhatsApp message via pywhatkit."
    parameters = {
        "type": "object",
        "properties": {
            "phone": {"type": "string", "description": "E.164 phone number e.g. +919876543210"},
            "message": {"type": "string", "description": "Message to send"}
        },
        "required": ["phone", "message"]
    }

    async def execute(self, phone: str, message: str) -> ToolResult:
        try:
            import pywhatkit
            # pywhatkit is synchronous and opens a browser — not suitable for headless servers
            # Stub: log and return partial
            return ToolResult(
                status="partial",
                message="WhatsApp sending requires a browser session. Not supported in headless/server mode.",
                data={"phone": phone},
                retryable=False
            )
        except Exception as e:
            return ToolResult(status="error", message=str(e), error=str(e))
