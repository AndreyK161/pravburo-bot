#!/bin/bash
set -euo pipefail

PROJECT_DIR="/home/botuser/pravburo-bot"
CHAT_ID="-1004466321275"
MESSAGE_THREAD_ID="7"

cd "$PROJECT_DIR"
source bot/.env  # даёт BOT_TOKEN

DUMP_FILE="$(date +%F)_dump.sql"

docker exec -i postgres_db pg_dump -U botuser bot_pravburo > "$DUMP_FILE"

curl -s -F "chat_id=${CHAT_ID}" -F "message_thread_id=${MESSAGE_THREAD_ID}" -F "document=@${DUMP_FILE}" \
    "https://api.telegram.org/bot${BOT_TOKEN}/sendDocument" > /dev/null


rm "$DUMP_FILE"