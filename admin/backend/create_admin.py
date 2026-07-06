import asyncio
import getpass

import asyncpg

from auth import hash_password
from config import DATABASE_URL


async def main() -> None:
    username = input("Логин: ").strip()
    password = getpass.getpass("Пароль: ")
    password_confirm = getpass.getpass("Пароль ещё раз: ")

    if password != password_confirm:
        print("Пароли не совпадают")
        return
    if not username or not password:
        print("Логин и пароль не могут быть пустыми")
        return

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        existing = await conn.fetchrow("SELECT id FROM admin_users WHERE username = $1", username)
        if existing:
            print(f"Пользователь '{username}' уже существует")
            return
        await conn.execute(
            "INSERT INTO admin_users (username, password_hash) VALUES ($1, $2)",
            username,
            hash_password(password),
        )
        print(f"Пользователь '{username}' создан")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
