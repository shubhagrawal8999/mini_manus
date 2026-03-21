#!/bin/bash
# Alternative startup script with additional checks
# Used if you need pre-start logic

echo "Starting Mini-Manus Bot..."

# Ensure data directory exists
mkdir -p /data

# Verify environment
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN not set"
    exit 1
fi

if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "ERROR: DEEPSEEK_API_KEY not set"
    exit 1
fi

echo "Environment validated"
echo "Database path: $DATABASE_PATH"

# Start bot
exec python -m bot.main
