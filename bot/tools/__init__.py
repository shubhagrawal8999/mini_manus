"""
Tool registry - auto-discovery pattern.
Add new tools here to make them available to the agent.
"""

from typing import Dict, List, Any
from bot.tools.email import EmailTool
from bot.tools.whatsapp import WhatsAppTool
from bot.tools.research import ResearchTool
from bot.tools.schedule import ScheduleTool

# Registry - add new tools here
TOOLS: Dict[str, Any] = {
    "send_email": EmailTool(),
    "send_whatsapp": WhatsAppTool(),
    "web_research": ResearchTool(),
    "schedule_task": ScheduleTool(),
    # Add new tools here - automatically available to LLM
}

def get_tool_schemas() -> List[Dict[str, Any]]:
    """Generate OpenAI-compatible function schemas."""
    schemas = []
    for name, tool in TOOLS.items():
        schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool.description,
                "parameters": tool.parameters
            }
        })
    return schemas

def get_tool(name: str) -> Any:
    """Get tool by name."""
    return TOOLS.get(name)

async def execute_tool(name: str, params: Dict) -> Dict[str, Any]:
    """Execute tool by name with params."""
    tool = get_tool(name)
    if not tool:
        return {
            "status": "error",
            "message": f"Tool '{name}' not found",
            "error": "Tool not registered"
        }
    
    result = await tool.run(**params)
    return result.dict()
