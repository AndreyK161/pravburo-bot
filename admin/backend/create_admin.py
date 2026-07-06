import asyncio
import getpass

import asyncpg

from auth import hash_password
from config import DATABASE_URL


VALID_ROLES = ("admin", "manager")


async def main() -> None:
    username = input("Логин: ").strip()
    password = getpass.getpass("Пароль: ")
    password_confirm = getpass.getpass("Пароль ещё раз: ")
    role = input(f"Роль ({'/'.join(VALID_ROLES)}) [admin]: ").strip() or "admin"

    if password != password_confirm:
        print("Пароли не совпадают")
        return
    if not username or not password:
        print("Логин и пароль не могут быть пустыми")
        return
    if role not in VALID_ROLES:
        print(f"Роль должна быть одной из: {', '.join(VALID_ROLES)}")
        return

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        existing = await conn.fetchrow("SELECT id FROM admin_users WHERE username = $1", username)
        if existing:
            print(f"Пользователь '{username}' уже существует")
            return
        await conn.execute(
            "INSERT INTO admin_users (username, password_hash, role) VALUES ($1, $2, $3)",
            username,
            hash_password(password),
            role,
        )
        print(f"Пользователь '{username}' создан с ролью '{role}'")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
