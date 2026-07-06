from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel

import database
from auth import create_session_token, hash_password, read_session_token, verify_password
from config import SESSION_COOKIE_NAME, SESSION_COOKIE_SECURE, SESSION_MAX_AGE_SECONDS

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


async def require_auth(session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)) -> dict:
    if not session:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    payload = read_session_token(session)
    if not payload:
        raise HTTPException(status_code=401, detail="Сессия истекла, войдите заново")
    return payload


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    async with database.DB_POOL.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, password_hash FROM admin_users WHERE username = $1", body.username
        )
        success = bool(row) and verify_password(body.password, row["password_hash"])

        await conn.execute(
            """
            INSERT INTO admin_login_logs (admin_user_id, username_attempted, success, ip_address, user_agent)
            VALUES ($1, $2, $3, $4, $5)
            """,
            row["id"] if row else None,
            body.username,
            success,
            ip_address,
            user_agent,
        )

    if not success:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    token = create_session_token(row["id"], row["username"])
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
    )
    return {"ok": True, "username": row["username"]}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
async def me(payload: dict = Depends(require_auth)):
    return {"username": payload["username"]}
