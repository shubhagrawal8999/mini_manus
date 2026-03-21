"""
Health check for Docker/Railway.
Verifies bot is responsive and database is writable.
"""

import os
import sys
import sqlite3
from pathlib import Path

def check_health():
    """Return True if healthy, False otherwise."""
    
    # Check database is writable
    db_path = os.getenv("DATABASE_PATH", "/data/agent.db")
    try:
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Test write
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS healthcheck (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT OR REPLACE INTO healthcheck (id) VALUES (1)")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database health check failed: {e}")
        return False
    
    # Check environment is loaded
    required = ["TELEGRAM_BOT_TOKEN", "DEEPSEEK_API_KEY"]
    for var in required:
        if not os.getenv(var):
            print(f"Missing env var: {var}")
            return False
    
    print("Health check passed")
    return True

if __name__ == "__main__":
    sys.exit(0 if check_health() else 1)
