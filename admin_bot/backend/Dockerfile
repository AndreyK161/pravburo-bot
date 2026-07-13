FROM python:3.13-slim

WORKDIR /app

COPY admin_bot/backend/requirements.txt admin_bot/backend/requirements.txt
RUN pip install --no-cache-dir -r admin_bot/backend/requirements.txt

COPY admin_bot/backend admin_bot/backend
COPY admin_bot/frontend admin_bot/frontend

WORKDIR /app/admin_bot/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
