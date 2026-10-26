from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

TOKEN = getenv("BOT_TOKEN")
DATABASE_URL = getenv("DATABASE_URL")

# Обычные напоминания отправляются только в этом окне по московскому времени.
# Безусловные шаги (always=true: кружки, истории и т.п.) ограничение не получают.
REMINDER_TIMEZONE = ZoneInfo(getenv("REMINDER_TIMEZONE", "Europe/Moscow"))
REMINDER_START_HOUR = 9
REMINDER_END_HOUR = 21

BASE_DIR = Path(__file__).parent.parent.parent  # bot_pravburo/tg_bot/app -> bot_pravburo
DATA_DIR = BASE_DIR / "data"
FILES_DIR = DATA_DIR / "files"
SCENARIO_PATH = DATA_DIR / "scenario.json"

# Блок, который никогда не редактируется поверх предыдущего сообщения —
# всегда шлётся заново, чтобы пользователь легко находил главное меню в чате.
NEVER_REPLACE_BLOCK = "general_menu"

# Пауза перед автопереходом (auto_next), чтобы сообщения цепочки не сыпались разом.
AUTO_NEXT_DELAY_SECONDS = 2.5

# Файлы с такими расширениями шлём как фото (send_photo), а не как документ —
# тогда в чате показывается превью картинки, а не иконка файла.
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# save_as из input-блоков и set_field из кнопок сценария, которым разрешено
# писаться в свою колонку users. Белый список нужен, чтобы имя поля из JSON
# нельзя было подставить в SQL как есть.
USER_FIELD_COLUMNS = {"name", "phone", "region", "has_property"}

# id блоков сценария, отмечающих начало и успешное завершение консультации.
# Если блок в scenario.json переименуют, эти константы нужно поправить вручную.
CONSULTATION_START_BLOCK = "consultation"
CONSULTATION_DONE_BLOCK = "consultation_contact"
TAG_CONSULTATION_STARTED = "Консультация: нет"
TAG_CONSULTATION_DONE = "Консультация: да"

# Блок согласия на обработку перс. данных — показывается один раз (после
# проверки подписки, до general_menu/цели диплинка), пока юзер не нажмёт
# кнопку "Даю согласие" в нём (см. consent_given_at в БД).
CONSENT_BLOCK = "consent"

# Чаты, куда шлём уведомление о новой заявке (человек дошёл до CONSULTATION_DONE_BLOCK,
# то есть оставил телефон). Бота нужно добавить в эти чаты обычным участником —
# для отправки сообщений права администратора не нужны. id чатов через запятую.
NOTIFY_CHAT_IDS = [int(x) for x in getenv("NOTIFY_CHAT_IDS", "").split(",") if x.strip()]

# Тот же момент (CONSULTATION_DONE_BLOCK) шлёт лид в Битрикс24 через входящий
# вебхук вида https://ваш-домен.bitrix24.ru/rest/1/xxxxxxxx (без /crm.lead.add.json
# на конце — путь метода добавляется в коде). BITRIX_SOURCE_ID_TG — значение
# поля "Источник" для лидов из Telegram (код из справочника CRM, необязателен —
# если не задан, поле просто не передаётся и Битрикс возьмёт свой дефолт).
BITRIX_WEBHOOK_URL = getenv("BITRIX_WEBHOOK_URL")
BITRIX_SOURCE_ID_TG = getenv("BITRIX_SOURCE_ID_TG")

# Антиспам: если юзер шлёт больше ANTISPAM_MAX_EVENTS сообщений/нажатий кнопок
# за ANTISPAM_WINDOW_SECONDS — считаем его спамером и молчим ANTISPAM_MUTE_SECONDS
# (ничего не обрабатываем и не отвечаем, кроме одного предупреждения при входе в мут).
ANTISPAM_WINDOW_SECONDS = 10
ANTISPAM_MAX_EVENTS = 8
ANTISPAM_MUTE_SECONDS = 60
