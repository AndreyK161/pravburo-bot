# Разнесённое развёртывание: БД в РФ, сервисы в Нидерландах

Схема: Postgres остаётся на сервере РФ, `tg_bot`/`vk_bot`/`admin` переезжают
на сервер NL. Соединение между серверами — приватный туннель WireGuard,
порт 5432 в публичный интернет не открывается вообще.

Файлы в репозитории:
- `docker-compose.yml` с `COMPOSE_PROFILES=db` — поднимать **только на сервере РФ**.
- `docker-compose.yml` с `COMPOSE_PROFILES=app` — на сервере NL.
- `.env-example` — актуальные переменные для обоих файлов.

## 1. Поднять WireGuard между серверами

На каждом сервере:

```bash
sudo apt update && sudo apt install -y wireguard
wg genkey | sudo tee /etc/wireguard/privatekey | wg pubkey | sudo tee /etc/wireguard/publickey
sudo chmod 600 /etc/wireguard/privatekey
```

**На сервере РФ** (`/etc/wireguard/wg0.conf`), адрес `10.10.10.1`:

```ini
[Interface]
Address = 10.10.10.1/24
PrivateKey = <приватный ключ сервера РФ>
ListenPort = 51820

[Peer]
PublicKey = <публичный ключ сервера NL>
AllowedIPs = 10.10.10.2/32
Endpoint = <публичный IP сервера NL>:51820
PersistentKeepalive = 25
```

**На сервере NL** (`/etc/wireguard/wg0.conf`), адрес `10.10.10.2`:

```ini
[Interface]
Address = 10.10.10.2/24
PrivateKey = <приватный ключ сервера NL>
ListenPort = 51820

[Peer]
PublicKey = <публичный ключ сервера РФ>
AllowedIPs = 10.10.10.1/32
Endpoint = <публичный IP сервера РФ>:51820
PersistentKeepalive = 25
```

Запуск и автозагрузка на обоих серверах:

```bash
sudo systemctl enable --now wg-quick@wg0
sudo wg show   # проверить, что handshake прошёл
```

Проверка связи: `ping 10.10.10.1` с сервера NL и `ping 10.10.10.2` с сервера РФ.

Если между серверами стоит облачный firewall (Timeweb/Selectel/Hetzner и т.п.,
не iptables на самой машине) — там тоже нужно явно разрешить UDP/51820 между
публичными IP серверов.

## 2. Firewall: закрыть 5432 наружу на сервере РФ

Порт 5432 должен слушать только на `10.10.10.1` (WireGuard), не на `0.0.0.0`.
Это уже обеспечивается биндом порта в профиле `db` файла `docker-compose.yml`
(`"${DB_BIND_ADDRESS}:5432:5432"`), но дополнительно закройте порт на уровне
firewall на всякий случай:

```bash
sudo ufw allow in on wg0 to any port 5432 proto tcp
sudo ufw deny 5432/tcp
```

## 3. Сервер РФ: поднять только БД

```bash
git clone <repo> && cd bot_pravburo
cp .env-example .env
# в .env выставить:
#   POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB — реальные значения
#   DB_BIND_ADDRESS=10.10.10.1
docker compose up -d
docker compose ps   # дождаться healthy
```

## 4. Перенос данных (если БД уже существует со старыми данными)

На старом сервере, где сейчас живёт единая связка:

```bash
docker exec -i postgres_db pg_dump -U <user> <db_name> > dump.sql
```

Скопировать `dump.sql` на сервер РФ (`scp`) и накатить в новую БД:

```bash
docker exec -i postgres_db psql -U <user> -d <db_name> < dump.sql
```

## 5. Сервер NL: поднять сервисы

```bash
git clone <repo> && cd bot_pravburo
cp .env-example .env
# в .env выставить:
#   POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB — те же значения, что на сервере РФ
#   DB_HOST=10.10.10.1
#   DB_PORT=5432
# плюс tg_bot/.env, vk_bot/.env, admin_bot/backend/.env как раньше (токены и т.д.)
docker compose up -d --build
docker compose logs -f tg_bot   # убедиться, что коннект к БД прошёл
```

## 6. Проверка

```bash
# На сервере NL — есть ли коннект к БД через туннель
docker exec -it pravburo_bot python -c "
import asyncio, asyncpg, os
async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    print(await conn.fetchval('select 1'))
asyncio.run(main())
"
```

## Заметки

- `admin_bot/backend` (alembic-миграции) можно гонять с любого места, у которого
  есть сетевой доступ к БД (например, прямо с сервера NL, раз туннель поднят) —
  выставите `DATABASE_URL` на реальный `10.10.10.1` перед `alembic upgrade head`.
- `dump_and_send.sh` (бэкап в Telegram) нужно перенести и адаптировать под
  сервер РФ — `docker exec -i postgres_db pg_dump ...` там теперь выполняется
  на сервере РФ, а не там, где раньше был единый compose.
- Если WireGuard недоступен (например, провайдер режет UDP), альтернатива —
  `autossh`-туннель: `autossh -M 0 -N -L 10.10.10.2:5432:localhost:5432 root@<IP_РФ>`
  как systemd-сервис на сервере NL, тогда `DB_HOST=127.0.0.1` в `.env` на NL.
