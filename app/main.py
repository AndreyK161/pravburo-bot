import asyncio

from aiogram import Bot

from config import TOKEN
from database import init_db_pool
from handlers import dp


async def main() -> None:
    await init_db_pool()
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
