"""
Schedule recurring tasks.
Stores tasks in SQLite; a background APScheduler worker polls and executes them.

BUG FIXED:
  `async with memory._init_db() or True:` was wrong — _init_db() is a plain
  coroutine, not an async context manager.  The `or True` hack silently
  swallowed the error.  Fixed by just calling `await memory._init_db()`.
"""

import asyncio
from datetime import datetime
from typing import Literal

from bot.tools.base import Tool, ToolResult
from bot.agent.memory import memory


class ScheduleTool(Tool):
    name = "schedule_task"
    description = (
        "Schedule a recurring or one-time automation task. "
        "Tasks are saved to the database and executed by the background scheduler. "
        "Use for LinkedIn posts, email follow-ups, research digests, or reminders."
    )

    parameters = {
        "type": "object",
        "properties": {
            "task_type": {
                "type": "string",
                "enum": [
                    "linkedin_post",
                    "email_followup",
                    "research_report",
                    "reminder",
                ],
                "description": "Type of task to schedule",
            },
            "frequency": {
                "type": "string",
                "enum": ["daily", "weekly", "thursday_friday", "once"],
                "description": "How often to run the task",
            },
            "prompt": {
                "type": "string",
                "description": "The instruction to execute each time the task fires",
            },
            "scheduled_time": {
                "type": "string",
                "description": "Time in HH:MM (24h) to run the task, e.g. '09:00'",
            },
        },
        "required": ["task_type", "frequency", "prompt"],
    }

    async def execute(
        self,
        task_type: Literal[
            "linkedin_post", "email_followup", "research_report", "reminder"
        ],
        frequency: Literal["daily", "weekly", "thursday_friday", "once"],
        prompt: str,
        scheduled_time: str = "09:00",
    ) -> ToolResult:

        # BUG FIX: just await the coroutine, don't use it as a context manager
        await memory._init_db()

        try:
            async with __import__("aiosqlite").connect(memory.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO scheduled_tasks
                        (user_id, task_type, frequency, prompt, is_active)
                    VALUES (0, ?, ?, ?, 1)
                    """,
                    (task_type, frequency, f"{scheduled_time}|{prompt}"),
                )
                await db.commit()

            return ToolResult(
                status="success",
                message=(
                    f"✅ Task '{task_type}' scheduled ({frequency} at {scheduled_time}).\n"
                    "It will run automatically via the background scheduler."
                ),
                data={
                    "task_type": task_type,
                    "frequency": frequency,
                    "scheduled_time": scheduled_time,
                    "prompt": prompt,
                },
            )

        except Exception as exc:
            return ToolResult(
                status="error",
                message=f"Scheduling failed: {exc}",
                error=str(exc),
                retryable=True,
            )
