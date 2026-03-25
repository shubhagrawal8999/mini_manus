"""
ReAct (Reasoning + Acting) orchestrator.

BUG FIXED:
  `result` variable was accessed after the loop ended but could be undefined
  if ALL iterations consumed tool calls and the LLM never returned a plain
  text response.  Added explicit `result` initialisation and a fallback
  final_response for that case.
"""

import json
import time
from typing import List, Dict, Any, Optional

from bot.config import router, Settings
from bot.agent.memory import memory
from bot.tools import get_tool_schemas, execute_tool


class Orchestrator:
    """
    ReAct loop: Reason → Act (tool call or final answer) → Observe → repeat.
    """

    MAX_ITERATIONS = 6  # guard against infinite tool-call loops

    async def process(self, user_id: int, message: str) -> Dict[str, Any]:
        """
        Process one user message end-to-end.
        Returns dict: response, tools_used, cost_usd, execution_time_ms, model.
        """
        start_time = time.time()

        context = await memory.get_context(user_id)
        messages = self._build_messages(context, message)

        tools_used: List[Dict] = []
        tool_failures: List[str] = []
        total_cost: float = 0.0
        final_response: str = ""

        # BUG FIX: initialise result so it's always defined after the loop
        result: Dict[str, Any] = {"model": "unknown", "usage": {"cost_usd": 0.0}}

        for iteration in range(self.MAX_ITERATIONS):
            result = await router.call(
                messages=messages,
                complexity="medium",
                tools=get_tool_schemas(),
            )

            if not result["success"]:
                final_response = f"❌ LLM error: {result.get('error', 'Unknown error')}"
                break

            total_cost += result["usage"]["cost_usd"]
            llm_message = result["content"]

            # ── Tool call branch ──────────────────────────────────────
            if llm_message.tool_calls:
                for tool_call in llm_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_params = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as exc:
                        tool_params = {}
                        err = f"Tool '{tool_name}' had invalid JSON arguments: {exc}"
                        tool_failures.append(err)
                        print(f"[Orchestrator] {err}")

                    tool_result = await execute_tool(tool_name, tool_params)
                    tools_used.append(
                        {"tool": tool_name, "params": tool_params, "result": tool_result}
                    )
                    if tool_result.get("status") in ("error", "partial"):
                        tool_failures.append(
                            f"{tool_name}: {tool_result.get('message', 'Tool failed')}"
                        )

                    # Feed result back into conversation
                    messages.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": json.dumps(tool_params),
                                    },
                                }
                            ],
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result),
                        }
                    )
                # Continue loop so LLM can react to the tool result
                continue

            # ── Final text response ───────────────────────────────────
            final_response = llm_message.content or ""
            break

        else:
            # Exhausted all iterations without a plain text response
            final_response = (
                "⚠️ I ran out of reasoning steps before finishing. "
                "Please try rephrasing your request."
            )

        if not final_response and tool_failures:
            final_response = (
                "⚠️ I could not complete your request because one or more tools failed:\n- "
                + "\n- ".join(tool_failures[:4])
            )
        elif final_response and tool_failures:
            final_response += (
                "\n\n⚠️ Tool diagnostics:\n- " + "\n- ".join(tool_failures[:3])
            )

        execution_time_ms = int((time.time() - start_time) * 1000)

        # Persist updated context
        updated_context = list(context)
        updated_context.append({"role": "user", "content": message})
        updated_context.append({"role": "assistant", "content": final_response})
        await memory.update_context(user_id, updated_context)

        # Audit log
        await memory.log_interaction(
            user_id=user_id,
            user_message=message,
            bot_response=final_response,
            tools_used=[t["tool"] for t in tools_used],
            execution_time_ms=execution_time_ms,
            cost_usd=total_cost,
            model_used=result.get("model", "unknown"),
        )

        return {
            "response": final_response,
            "tools_used": tools_used,
            "cost_usd": total_cost,
            "execution_time_ms": execution_time_ms,
            "model": result.get("model", "unknown"),
        }

    # ──────────────────────────────────────────────────────────────────
    def _build_messages(self, context: List[Dict], new_message: str) -> List[Dict]:
        system_prompt = f"""You are Mini-Manus, an autonomous AI agent that helps users automate tasks.

Available tools:
- send_email        : Send emails via Gmail
- send_whatsapp     : Send WhatsApp messages (headless server — limited support)
- web_research      : Search the web and summarise results
- schedule_task     : Schedule recurring tasks
- post_linkedin     : Post text updates to LinkedIn

Rules:
1. Use a tool when the user clearly wants an action (send, post, research, schedule).
2. Respond directly for questions, conversation, or when no tool applies.
3. If a tool fails, explain exact failure reason (configuration, auth, validation, network).
4. Be concise but complete.
5. Today is {time.strftime('%A, %Y-%m-%d %H:%M:%S')}.

When calling tools, infer parameters from the user's natural language."""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(context)
        messages.append({"role": "user", "content": new_message})
        return messages


# Singleton
orchestrator = Orchestrator()
