from os import getenv
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = getenv("DATABASE_URL")
BOT_TOKEN = getenv("BOT_TOKEN")

BROADCAST_DELAY_SECONDS = 0.05

BASE_DIR = Path(__file__).parent.parent.parent  # bot_pravburo/admin/backend -> bot_pravburo
DATA_DIR = BASE_DIR / "data"
SCENARIO_PATH = DATA_DIR / "scenario.json"
SCENARIO_BACKUP_DIR = DATA_DIR / "scenario_backups"
FILES_DIR = DATA_DIR / "files"

# Должно совпадать с app/config.py (USER_FIELD_COLUMNS) и app/validators.py (VALIDATORS)
# бота — это те же самые белые списки, продублированные тут для валидации сценария.
SAVE_AS_FIELDS = ["name", "phone", "region"]
VALIDATOR_NAMES = ["phone"]

BLOCK_TYPES = ["message", "document", "input", "condition", "delay"]
BLOCK_REQUIRED_FIELDS = {
    "message": ["text"],
    "document": ["text", "file"],
    "input": ["text", "save_as", "next"],
    "condition": ["channel", "yes", "no"],
    "delay": ["seconds", "next"],
}
