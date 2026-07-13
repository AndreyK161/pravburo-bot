FROM python:3.13-slim

WORKDIR /app

COPY bot/requirements.txt bot/requirements.txt
RUN pip install --no-cache-dir -r bot/requirements.txt

COPY bot/app bot/app

WORKDIR /app/bot
CMD ["python", "app/main.py"]
