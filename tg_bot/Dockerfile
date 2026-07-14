FROM python:3.13-slim

WORKDIR /app

COPY tg_bot/requirements.txt tg_bot/requirements.txt
RUN pip install --no-cache-dir -r tg_bot/requirements.txt

COPY tg_bot/app tg_bot/app

WORKDIR /app/tg_bot
CMD ["python", "app/main.py"]
