from os import getenv
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = getenv("DATABASE_URL")
BOT_TOKEN = getenv("BOT_TOKEN")
VK_TOKEN = getenv("VK_TOKEN")

# Telegram Bot API разрешает ~30 сообщений/сек суммарно разным чатам.
# Держим темп запуска новых отправок чуть ниже лимита (с запасом на джиттер
# сети), а конкурентность ограничиваем отдельно — чтобы не накопить лавину
# одновременных запросов, если Telegram вдруг начал отвечать медленнее обычного.
BROADCAST_RATE_PER_SECOND = 20
BROADCAST_MAX_CONCURRENCY = 30

SESSION_SECRET_KEY = getenv("SESSION_SECRET_KEY")
SESSION_COOKIE_NAME = "admin_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12  # 12 часов
# Cookie должна быть Secure только когда сайт реально отдаётся по HTTPS -
# иначе браузер её просто не отправит и логин будет всегда падать.
SESSION_COOKIE_SECURE = getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

BASE_DIR = Path(__file__).parent.parent.parent  # bot_pravburo/admin_bot/backend -> bot_pravburo
DATA_DIR = BASE_DIR / "data"
FILES_DIR = DATA_DIR / "files"

# Разные боты — разные сценарии. tg_bot и vk_bot пока делят один и тот же
# scenario.json ("tg_vk"), будущий Instagram-бот получит свой ("instagram") —
# отдельные файлы, бэкапы и раскладка графа, чтобы блоки/координаты одного
# сценария не путались с другим. DEFAULT_SCENARIO_PLATFORM — та, что открывается
# по умолчанию (совпадает с тем, что сейчас реально крутится в проде).
DEFAULT_SCENARIO_PLATFORM = "tg_vk"
SCENARIO_PLATFORMS = {
    "tg_vk": {
        "label": "TG / VK",
        "path": DATA_DIR / "scenario.json",
        "backup_dir": DATA_DIR / "scenario_backups",
        "positions_path": DATA_DIR / "scenario_graph_positions.json",
    },
    "instagram": {
        "label": "Instagram",
        "path": DATA_DIR / "scenario_instagram.json",
        "backup_dir": DATA_DIR / "scenario_backups_instagram",
        "positions_path": DATA_DIR / "scenario_graph_positions_instagram.json",
    },
}

# Должно совпадать с tg_bot/app/config.py (USER_FIELD_COLUMNS) и tg_bot/app/validators.py (VALIDATORS)
# бота — это те же самые белые списки, продублированные тут для валидации сценария.
SAVE_AS_FIELDS = ["name", "phone", "region"]
VALIDATOR_NAMES = ["phone"]
# set_field у кнопок (см. tg_bot/app/config.py USER_FIELD_COLUMNS) — отдельно от SAVE_AS_FIELDS,
# так как это не поле input-блока, а значение, которое запоминает нажатие кнопки.
BUTTON_SET_FIELDS = ["has_property"]

BLOCK_TYPES = ["message", "document", "input", "condition", "delay"]
BLOCK_REQUIRED_FIELDS = {
    "message": ["text"],
    "document": ["text", "file"],
    "input": ["text", "save_as", "next"],
    "condition": ["channel", "yes", "no"],
    "delay": ["seconds", "next"],
}

# Должно совпадать с tg_bot/app/config.py — id блоков, при входе в которые бот
# автоматически проставляет юзеру тег (используется страницей графа сценария).
CONSULTATION_START_BLOCK = "consultation"
CONSULTATION_DONE_BLOCK = "consultation_contact"
TAG_CONSULTATION_STARTED = "Консультация: нет"
TAG_CONSULTATION_DONE = "Консультация: да"
