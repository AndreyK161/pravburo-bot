# Шпаргалка команд. Профиль (db/app) берётся из COMPOSE_PROFILES в .env.
.DEFAULT_GOAL := help
.PHONY: help up down build restart logs ps migrate test dev-db dev-admin dev-tg dev-vk

help:  ## Список команд
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

up:  ## Пересобрать и поднять всё, что выбрано в COMPOSE_PROFILES
	docker compose up -d --build

down:  ## Остановить
	docker compose down

build:  ## Только собрать образы
	docker compose build

restart:  ## Перезапустить (make restart s=admin — один сервис)
	docker compose restart $(s)

logs:  ## Логи (make logs s=tg_bot — один сервис)
	docker compose logs -f --tail=100 $(s)

ps:  ## Статус контейнеров
	docker compose ps

migrate:  ## Миграции БД (alembic upgrade head)
	docker compose run --rm admin alembic upgrade head

test:  ## Тесты обоих ботов (нужна БД из dev-db)
	cd tg_bot && .venv/bin/pytest -q
	cd vk_bot && .venv/bin/pytest -q

# --- Локальная разработка: БД в docker, всё остальное — прямо с хоста ---
dev-db:  ## Локальный Postgres на 127.0.0.1:5432
	DB_BIND_ADDRESS=127.0.0.1 docker compose --profile db up -d db

dev-admin:  ## Админка с автоперезагрузкой на :8199
	cd admin_bot/backend && .venv/bin/uvicorn main:app --reload --port 8199

dev-tg:  ## Telegram-бот локально
	cd tg_bot && .venv/bin/python app/main.py

dev-vk:  ## VK-бот локально
	cd vk_bot && .venv/bin/python app/main.py
