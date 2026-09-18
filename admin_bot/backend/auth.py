from datetime import datetime, timedelta, timezone

import bcrypt
import jwt as pyjwt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import (
    REFRESH_MAX_AGE_SECONDS,
    SESSION_SECRET_KEY,
    SESSION_MAX_AGE_SECONDS,
    SSO_JWT_ALGORITHM,
    SSO_JWT_SECRET,
)

_serializer = URLSafeTimedSerializer(SESSION_SECRET_KEY, salt="admin-session")
# Отдельная соль — чтобы refresh-токен нельзя было подсунуть вместо обычной сессионной
# куки (и наоборот), хотя ключ подписи один и тот же.
_refresh_serializer = URLSafeTimedSerializer(SESSION_SECRET_KEY, salt="admin-refresh")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_session_token(admin_user_id: int, username: str, role: str) -> str:
    return _serializer.dumps({"admin_user_id": admin_user_id, "username": username, "role": role})


def read_session_token(token: str) -> dict | None:
    try:
        return _serializer.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


def create_refresh_token(admin_user_id: int, username: str, role: str) -> str:
    return _refresh_serializer.dumps({"admin_user_id": admin_user_id, "username": username, "role": role})


def read_refresh_token(token: str) -> dict | None:
    try:
        return _refresh_serializer.loads(token, max_age=REFRESH_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


def verify_sso_token(token: str) -> dict | None:
    # Токен выдаёт LK-хаб (admin_panel_service), подписан общим SSO_JWT_SECRET —
    # см. PravBuroLK/services/client_search_service/backend/app/auth.py:require_staff
    # для того же паттерна (доверяем claim'ам, без похода в чужую БД).
    if not SSO_JWT_SECRET:
        return None
    try:
        return pyjwt.decode(token, SSO_JWT_SECRET, algorithms=[SSO_JWT_ALGORITHM])
    except pyjwt.InvalidTokenError:
        return None


def create_lk_sso_token(username: str) -> str:
    # Обратное направление: наша сессия -> одноразовый (2 мин) JWT, который LK примет
    # на своём /sso и заведёт localStorage-сессию по совпадающему username в её БД
    # (см. PravBuroLK/services/admin_panel_service/backend/app/auth.py:get_current_user —
    # там резолвинг по username как раз под такие "чужие" токены).
    payload = {
        "sub": "0",
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=2),
    }
    return pyjwt.encode(payload, SSO_JWT_SECRET, algorithm=SSO_JWT_ALGORITHM)
