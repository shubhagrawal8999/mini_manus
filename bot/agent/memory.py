"""
Async SQLite persistence with connection pooling.
Critical: Database file must be at /data/agent.db (Railway volume).
"""

import aiosqlite
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from bot.config import Settings

class Memory:
    """
    Persistent memory for conversation history and audit logs.
    Uses aiosqlite for async operations.
    """
    
    def __init__(self):
        self.db_path = Settings.DATABASE_PATH
        self._init_done = False
    
    async def _init_db(self):
        """Initialize tables if not exist."""
        if self._init_done:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            # Sessions: Current conversation context per user
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id INTEGER PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    context_json TEXT DEFAULT '{}'
                )
            """)
            
            # Interactions: Audit log
            await db.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_message TEXT,
                    bot_response TEXT,
                    tools_used TEXT,  -- JSON array
                    execution_time_ms INTEGER,
                    cost_usd REAL,
                    model_used TEXT
                )
            """)
            
            # Scheduled tasks
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    task_type TEXT,
                    frequency TEXT,
                    prompt TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            await db.commit()
            self._init_done = True
    
    async def get_context(self, user_id: int) -> List[Dict]:
        """Get conversation history for user."""
        await self._init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT context_json FROM sessions WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                context = json.loads(row['context_json'])
                # Return last 10 messages to manage token limit
                return context.get('messages', [])[-10:]
            return []
    
    async def update_context(self, user_id: int, messages: List[Dict]):
        """Update conversation history."""
        await self._init_db()
        
        context = {"messages": messages[-20:]}  # Keep last 20
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO sessions (user_id, context_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    context_json = excluded.context_json,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, json.dumps(context)))
            await db.commit()
    
    async def log_interaction(
        self,
        user_id: int,
        user_message: str,
        bot_response: str,
        tools_used: List[str],
        execution_time_ms: int,
        cost_usd: float,
        model_used: str
    ):
        """Log interaction for analytics."""
        await self._init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO interactions 
                (user_id, user_message, bot_response, tools_used, execution_time_ms, cost_usd, model_used)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                user_message,
                bot_response,
                json.dumps(tools_used),
                execution_time_ms,
                cost_usd,
                model_used
            ))
            await db.commit()
    
    async def get_stats(self, user_id: int) -> Dict[str, Any]:
        """Get usage stats for user."""
        await self._init_db()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Total interactions
            cursor = await db.execute(
                "SELECT COUNT(*) as count FROM interactions WHERE user_id = ?",
                (user_id,)
            )
            total = (await cursor.fetchone())['count']
            
            # Total cost
            cursor = await db.execute(
                "SELECT SUM(cost_usd) as total FROM interactions WHERE user_id = ?",
                (user_id,)
            )
            cost = (await cursor.fetchone())['total'] or 0
            
            # Recent tools used
            cursor = await db.execute(
                """SELECT tools_used FROM interactions 
                   WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10""",
                (user_id,)
            )
            rows = await cursor.fetchall()
            tools = []
            for row in rows:
                tools.extend(json.loads(row['tools_used']))
            
            return {
                "total_interactions": total,
                "total_cost_usd": round(cost, 4),
                "recent_tools": list(set(tools))
            }

# Global instance
memory = Memory()
