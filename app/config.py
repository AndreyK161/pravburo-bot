from os import getenv
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TOKEN = getenv("BOT_TOKEN")
DATABASE_URL = getenv("DATABASE_URL")

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
FILES_DIR = DATA_DIR / "files"
SCENARIO_PATH = DATA_DIR / "scenario.json"

# Блок, который никогда не редактируется поверх предыдущего сообщения —
# всегда шлётся заново, чтобы пользователь легко находил главное меню в чате.
NEVER_REPLACE_BLOCK = "general_menu"

# Пауза перед автопереходом (auto_next), чтобы сообщения цепочки не сыпались разом.
AUTO_NEXT_DELAY_SECONDS = 1.5

# Файлы с такими расширениями шлём как фото (send_photo), а не как документ —
# тогда в чате показывается превью картинки, а не иконка файла.
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# save_as из input-блоков, которым разрешено писаться в свою колонку users.
# Белый список нужен, чтобы имя поля из JSON нельзя было подставить в SQL как есть.
USER_FIELD_COLUMNS = {"name", "phone", "region"}
