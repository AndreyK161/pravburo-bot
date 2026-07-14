import asyncio

from database import init_db_pool
from handlers import bot


async def main() -> None:
    await init_db_pool()
    await bot.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
