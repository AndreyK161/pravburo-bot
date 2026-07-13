import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import SESSION_SECRET_KEY, SESSION_MAX_AGE_SECONDS

_serializer = URLSafeTimedSerializer(SESSION_SECRET_KEY, salt="admin-session")


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
