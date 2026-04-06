CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS user_preferences (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding vector(384),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS error_log (
    id SERIAL PRIMARY KEY,
    error_signature TEXT UNIQUE,
    error_type TEXT,
    context TEXT,
    attempted_fix TEXT,
    success BOOLEAN,
    times_occurred INT DEFAULT 1,
    last_seen TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pref_embedding ON user_preferences USING ivfflat (embedding vector_cosine_ops);
