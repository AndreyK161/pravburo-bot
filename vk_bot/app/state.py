# Счётчик активности на пользователя: растёт при каждом действии.
# Задержки сверяются с ним, чтобы не сработать, если юзер уже сделал что-то ещё.
USER_ACTIVITY: dict[int, int] = {}

# Последнее сообщение бота на пользователя — то, что заменяем при переходе между
# блоками. В отличие от tg_bot (там хранится сам aiogram Message с .edit_text()),
# VK API для редактирования сообщения (messages.edit) требует peer_id и message_id
# отдельными аргументами, поэтому здесь храним словарь {"peer_id":, "message_id":}.
LAST_BOT_MESSAGE: dict[int, dict] = {}

# Если юзер сейчас в блоке "input" — храним, куда сохранить его ответ и что
# показать дальше. Пока это так, fallback-обработчик не шлёт "вернитесь в меню".
AWAITING_INPUT: dict[int, dict] = {}

# Собранные от пользователей ответы (имя, телефон и т.п.): user_id -> {"name": "..."}
USER_DATA: dict[int, dict] = {}

# Антиспам: времена (time.monotonic()) последних сообщений/нажатий кнопок на пользователя,
# и до какого момента он "замьючен" за флуд — см. antispam.py.
SPAM_EVENT_TIMES: dict[int, list[float]] = {}
SPAM_MUTED_UNTIL: dict[int, float] = {}


def touch(user_id: int) -> int:
    USER_ACTIVITY[user_id] = USER_ACTIVITY.get(user_id, 0) + 1
    return USER_ACTIVITY[user_id]
