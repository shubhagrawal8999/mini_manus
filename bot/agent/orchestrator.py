"""
ReAct (Reasoning + Acting) orchestrator.
Decomposes tasks, executes tools, maintains context.
"""

import json
import time
from typing import List, Dict, Any, Optional
from bot.config import router, Settings
from bot.agent.memory import memory
from bot.tools import get_tool_schemas, execute_tool

class Orchestrator:
    """
    Main agent orchestrator using ReAct pattern:
    1. Reason about task
    2. Act (use tool or respond)
    3. Observe result
    4. Repeat until complete
    """
    
    def __init__(self):
        self.max_iterations = 5  # Prevent infinite loops
    
    async def process(self, user_id: int, message: str) -> Dict[str, Any]:
        """
        Process user message through full agent loop.
        Returns dict with response, cost, tools used.
        """
        start_time = time.time()
        
        # Load context
        context = await memory.get_context(user_id)
        
        # Build messages for LLM
        messages = self._build_messages(context, message)
        
        tools_used = []
        total_cost = 0
        final_response = ""
        
        # ReAct loop
        for iteration in range(self.max_iterations):
            # Call LLM with tool options
            result = await router.call(
                messages=messages,
                complexity="medium",
                tools=get_tool_schemas()
            )
            
            if not result["success"]:
                final_response = f"Error: {result.get('error', 'Unknown error')}"
                break
            
            # Track cost
            total_cost += result["usage"]["cost_usd"]
            
            llm_message = result["content"]
            
            # Check if tool call requested
            if llm_message.tool_calls:
                for tool_call in llm_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_params = json.loads(tool_call.function.arguments)
                    
                    # Execute tool
                    tool_result = await execute_tool(tool_name, tool_params)
                    tools_used.append({
                        "tool": tool_name,
                        "params": tool_params,
                        "result": tool_result
                    })
                    
                    # Add tool result to conversation
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(tool_params)
                            }
                        }]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result)
                    })
            else:
                # Final response
                final_response = llm_message.content
                break
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Update context
        context.append({"role": "user", "content": message})
        context.append({"role": "assistant", "content": final_response})
        await memory.update_context(user_id, context)
        
        # Log interaction
        await memory.log_interaction(
            user_id=user_id,
            user_message=message,
            bot_response=final_response,
            tools_used=[t["tool"] for t in tools_used],
            execution_time_ms=execution_time,
            cost_usd=total_cost,
            model_used=result.get("model", "unknown")
        )
        
        return {
            "response": final_response,
            "tools_used": tools_used,
            "cost_usd": total_cost,
            "execution_time_ms": execution_time,
            "model": result.get("model", "unknown")
        }
    
    def _build_messages(self, context: List[Dict], new_message: str) -> List[Dict]:
        """Build message list for LLM with system prompt and context."""
        
        system_prompt = f"""You are Mini-Manus, an autonomous AI agent that helps users automate tasks.
You have access to tools. Use them when needed, respond directly when appropriate.

Available tools:
- send_email: Send emails via Gmail
- send_whatsapp: Send WhatsApp messages  
- web_research: Search the web and extract information
- schedule_task: Schedule recurring tasks

Guidelines:
1. If user asks to send email/message/research, use the appropriate tool
2. If user asks something simple, respond directly
3. If tool fails, explain the error and suggest alternatives
4. Be concise but helpful
5. Current time: {time.strftime('%Y-%m-%d %H:%M:%S')}

When using tools, provide clear parameters based on user request."""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(context)
        messages.append({"role": "user", "content": new_message})
        
        return messages

# Global instance
orchestrator = Orchestrator()
