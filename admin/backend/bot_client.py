from aiogram import Bot

from config import BOT_TOKEN

bot: Bot | None = None


async def init_bot() -> None:
    global bot
    bot = Bot(token=BOT_TOKEN)


async def close_bot() -> None:
    if bot is not None:
        await bot.session.close()
