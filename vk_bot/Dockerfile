FROM python:3.13-slim

WORKDIR /app

COPY vk_bot/requirements.txt vk_bot/requirements.txt
RUN pip install --no-cache-dir -r vk_bot/requirements.txt

COPY vk_bot/app vk_bot/app

WORKDIR /app/vk_bot
CMD ["python", "app/main.py"]
