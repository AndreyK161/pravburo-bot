import asyncio

from aiogram import Bot

from config import TOKEN
from database import init_db_pool
from handlers import dp
from scheduler import run_scheduler


async def main() -> None:
    await init_db_pool()
    bot = Bot(token=TOKEN)
    scheduler_task = asyncio.create_task(run_scheduler(bot))
    try:
        await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
