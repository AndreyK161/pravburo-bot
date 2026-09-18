from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

import database
from auth import (
    create_lk_sso_token,
    create_refresh_token,
    create_session_token,
    hash_password,
    read_refresh_token,
    read_session_token,
    verify_password,
    verify_sso_token,
)
from config import (
    LK_ADMIN_URL,
    REFRESH_COOKIE_NAME,
    REFRESH_MAX_AGE_SECONDS,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SECURE,
    SESSION_MAX_AGE_SECONDS,
    SSO_ROLE_MAP,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


def _set_auth_cookies(response: Response, admin_user_id: int, username: str, role: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(admin_user_id, username, role),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
    )
    # Скользящее окно — обновляем refresh-куку на каждый её удачный обмен на сессию,
    # чтобы 7 дней отсчитывались от последней активности, а не от первого логина.
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        create_refresh_token(admin_user_id, username, role),
        max_age=REFRESH_MAX_AGE_SECONDS,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
    )


async def require_auth(
    response: Response,
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    admin_refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> dict:
    payload = read_session_token(session) if session else None
    if payload and "role" in payload:
        return payload

    # Сессия протухла (12ч) или её вовсе нет — пробуем длинный refresh (7 дней),
    # чтобы не гонять на /login при каждом чуть более долгом перерыве в работе.
    refresh_payload = read_refresh_token(admin_refresh) if admin_refresh else None
    if not refresh_payload or "role" not in refresh_payload:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    _set_auth_cookies(response, refresh_payload["admin_user_id"], refresh_payload["username"], refresh_payload["role"])
    return refresh_payload


def require_role(*allowed_roles: str):
    async def checker(payload: dict = Depends(require_auth)) -> dict:
        if payload.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        return payload

    return checker


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    async with database.DB_POOL.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, password_hash, role FROM admin_users WHERE username = $1", body.username
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

    _set_auth_cookies(response, row["id"], row["username"], row["role"])
    return {"ok": True, "username": row["username"], "role": row["role"]}


@router.get("/sso")
async def sso_login(token: str):
    # Единый вход из LK-хаба (admin_panel_service) — LK уже залогинил юзера
    # и передаёт сюда свой JWT ссылкой. Проверяем подпись общим секретом,
    # доверяем ролям из токена, заводим свою обычную сессионную куку — БД
    # не трогаем, отдельная запись в admin_users для SSO-входа не нужна.
    payload = verify_sso_token(token)
    if not payload or not payload.get("is_staff"):
        return RedirectResponse(url="/login?sso_failed=1")

    role = SSO_ROLE_MAP.get(payload.get("role"))
    if not role:
        return RedirectResponse(url="/login?sso_failed=1")

    username = payload.get("username") or f"lk_{payload.get('sub', '?')}"

    redirect = RedirectResponse(url="/")
    _set_auth_cookies(redirect, 0, username, role)
    return redirect


@router.get("/sso-to-lk")
async def sso_to_lk(payload: dict = Depends(require_auth)):
    # Обратное направление переключалки панелей — сама LK уже умеет резолвить такой
    # токен по username (см. её get_current_user), поэтому от нас требуется только
    # его выпустить и передать в query, а не заводить у себя копию сессии LK.
    token = create_lk_sso_token(payload["username"])
    return RedirectResponse(url=f"{LK_ADMIN_URL}/sso?token={token}")


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(REFRESH_COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
async def me(payload: dict = Depends(require_auth)):
    return {"username": payload["username"], "role": payload["role"]}
