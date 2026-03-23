"""
Minimal HTTP server for Railway healthcheck.
Runs alongside the Telegram polling bot in a background thread.
"""

from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}
