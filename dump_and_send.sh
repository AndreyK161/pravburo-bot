#!/bin/bash
set -euo pipefail

PROJECT_DIR="/home/botuser/pravburo-bot"
CHAT_ID="-1004327365114"
MESSAGE_THREAD_ID="8"

# WireGuard-адрес сервера БД (РФ) — см. deploy/SPLIT_DEPLOYMENT.md
DB_HOST="10.10.10.1"
DB_PORT="5432"

cd "$PROJECT_DIR"
source tg_bot/.env  # даёт BOT_TOKEN
source .env      # даёт POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB

DUMP_FILE="$(date +%F)_dump.sql"

# БД теперь на другом сервере (РФ) — снимаем дамп по сети через WireGuard,
# а не docker exec в локальный контейнер (postgres_db больше не на этой машине).
docker run --rm --network host -e PGPASSWORD="$POSTGRES_PASSWORD" postgres:16-alpine \
    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$DUMP_FILE"

curl -s -F "chat_id=${CHAT_ID}" -F "message_thread_id=${MESSAGE_THREAD_ID}" -F "document=@${DUMP_FILE}" \
    "https://api.telegram.org/bot${BOT_TOKEN}/sendDocument" > /dev/null


rm "$DUMP_FILE"