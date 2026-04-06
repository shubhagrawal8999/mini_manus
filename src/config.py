import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")
    REDIS_URL = os.getenv("REDIS_URL", None)
    
    # Model routing
    DEFAULT_MODEL = "deepseek"   # or "openai"
    OPENAI_MODEL = "gpt-4-turbo"
    DEEPSEEK_MODEL = "deepseek-chat"
    
    # Memory
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    VECTOR_DIM = 384   # for MiniLM
    
    # Self-repair
    MAX_RETRIES = 3
    ERROR_TABLE = "error_log"
    PREFERENCES_TABLE = "user_preferences"
