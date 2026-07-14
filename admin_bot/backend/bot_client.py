from aiogram import Bot
from vkbottle import API as VkApi

from config import BOT_TOKEN, VK_TOKEN

bot: Bot | None = None
vk_api: VkApi | None = None


async def init_bot() -> None:
    global bot
    bot = Bot(token=BOT_TOKEN)


async def close_bot() -> None:
    if bot is not None:
        await bot.session.close()


async def init_vk_api() -> None:
    global vk_api
    vk_api = VkApi(token=VK_TOKEN)


async def close_vk_api() -> None:
    if vk_api is not None:
        await vk_api.http_client.close()
