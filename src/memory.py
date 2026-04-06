import asyncpg
import json
from sentence_transformers import SentenceTransformer
from src.config import Config
from typing import List, Dict, Any
import hashlib

class MemoryManager:
    def __init__(self):
        self.encoder = SentenceTransformer(Config.EMBEDDING_MODEL)
        self.pool = None
    
    async def init_db(self):
        self.pool = await asyncpg.create_pool(Config.DATABASE_URL)
        # Ensure pgvector extension and tables exist
        await self.pool.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await self.pool.execute(f"""
            CREATE TABLE IF NOT EXISTS {Config.PREFERENCES_TABLE} (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding vector({Config.VECTOR_DIM}),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await self.pool.execute(f"""
            CREATE TABLE IF NOT EXISTS {Config.ERROR_TABLE} (
                id SERIAL PRIMARY KEY,
                error_signature TEXT UNIQUE,
                error_type TEXT,
                context TEXT,
                attempted_fix TEXT,
                success BOOLEAN,
                times_occurred INT DEFAULT 1,
                last_seen TIMESTAMP DEFAULT NOW()
            )
        """)
        # Create vector index
        await self.pool.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_pref_embedding 
            ON {Config.PREFERENCES_TABLE} USING ivfflat (embedding vector_cosine_ops)
        """)
    
    async def store_preference(self, user_id: str, text: str, metadata: Dict[str, Any]):
        embedding = self.encoder.encode(text).tolist()
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {Config.PREFERENCES_TABLE} (user_id, text, embedding, metadata)
                VALUES ($1, $2, $3, $4)
            """, user_id, text, embedding, json.dumps(metadata))
    
    async def retrieve_preferences(self, user_id: str, query: str, top_k: int = 3) -> List[Dict]:
        query_emb = self.encoder.encode(query).tolist()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT text, metadata, embedding <=> $1 AS distance
                FROM {Config.PREFERENCES_TABLE}
                WHERE user_id = $2
                ORDER BY distance
                LIMIT $3
            """, query_emb, user_id, top_k)
        return [{"text": r["text"], "metadata": r["metadata"], "distance": r["distance"]} for r in rows]
    
    async def store_error_fix(self, error_signature: str, error_type: str, context: str, fix: str, success: bool):
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {Config.ERROR_TABLE} (error_signature, error_type, context, attempted_fix, success)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (error_signature) DO UPDATE SET
                    times_occurred = {Config.ERROR_TABLE}.times_occurred + 1,
                    last_seen = NOW(),
                    attempted_fix = EXCLUDED.attempted_fix,
                    success = EXCLUDED.success
            """, error_signature, error_type, context, fix, success)
    
    async def get_fix_for_error(self, error_signature: str) -> str | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(f"""
                SELECT attempted_fix FROM {Config.ERROR_TABLE}
                WHERE error_signature = $1 AND success = true
                ORDER BY times_occurred DESC
                LIMIT 1
            """, error_signature)
        return row["attempted_fix"] if row else None
    
    @staticmethod
    def compute_signature(error: Exception, context: str) -> str:
        data = f"{type(error).__name__}:{str(error)}:{context[:200]}"
        return hashlib.sha256(data.encode()).hexdigest()
