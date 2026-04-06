FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg \
    && npx playwright install-deps \
    && apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium

COPY . .

# Use shell form so $PORT is expanded, with fallback to 8000
CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
