from aiogram.types import Message

# Счётчик активности на пользователя: растёт при каждом действии.
# Задержки сверяются с ним, чтобы не сработать, если юзер уже сделал что-то ещё.
USER_ACTIVITY: dict[int, int] = {}

# Последнее сообщение бота на пользователя — то, что заменяем при переходе между блоками.
LAST_BOT_MESSAGE: dict[int, Message] = {}

# Если юзер сейчас в блоке "input" — храним, куда сохранить его ответ и что
# показать дальше. Пока это так, fallback_text_handler не шлёт "вернитесь в меню".
AWAITING_INPUT: dict[int, dict] = {}

# Собранные от пользователей ответы (имя, телефон и т.п.): user_id -> {"name": "..."}
USER_DATA: dict[int, dict] = {}


def touch(user_id: int) -> int:
    USER_ACTIVITY[user_id] = USER_ACTIVITY.get(user_id, 0) + 1
    return USER_ACTIVITY[user_id]
