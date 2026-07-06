from os import getenv
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = getenv("DATABASE_URL")

BASE_DIR = Path(__file__).parent.parent.parent  # bot_pravburo/admin/backend -> bot_pravburo
DATA_DIR = BASE_DIR / "data"
SCENARIO_PATH = DATA_DIR / "scenario.json"
SCENARIO_BACKUP_DIR = DATA_DIR / "scenario_backups"
