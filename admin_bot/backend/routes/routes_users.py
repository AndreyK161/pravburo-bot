from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import database

router = APIRouter(prefix="/api/users", tags=["users"])

# Белый список полей, по которым разрешено фильтровать - имя поля из query
# нельзя подставлять в SQL как есть.
FILTERABLE_FIELDS = {
    "username": "u.username",
    "name": "u.name",
    "phone": "u.phone",
    "region": "u.region",
    "source": "u.source",
    "user_id": "u.user_id::TEXT",
}

# Платформа тоже белый список - имя таблицы нельзя подставлять в SQL как есть.
PLATFORM_TABLES = {"tg": "tg_users", "vk": "vk_users"}

USERS_UNION = " UNION ALL ".join(
    f"SELECT *, '{platform}' AS platform FROM {table}" for platform, table in PLATFORM_TABLES.items()
)


class TagAssignIn(BaseModel):
    tag_id: int | None


@router.get("")
async def list_users(
    tag_id: int | None = None,
    platform: str | None = None,
    field: str | None = None,
    value: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    conditions = []
    params = []

    if platform is not None:
        if platform not in PLATFORM_TABLES:
            raise HTTPException(status_code=422, detail=f"Неизвестная платформа: {platform}")
        params.append(platform)
        conditions.append(f"u.platform = ${len(params)}")

    if tag_id is not None:
        params.append(tag_id)
        conditions.append(f"u.tag_id = ${len(params)}")

    if field and value:
        column = FILTERABLE_FIELDS.get(field)
        if not column:
            raise HTTPException(status_code=422, detail=f"Неизвестное поле для фильтра: {field}")
        params.append(f"%{value}%")
        conditions.append(f"{column} ILIKE ${len(params)}")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_query = f"SELECT COUNT(*) FROM ({USERS_UNION}) u {where_clause}"

    params.append(page_size)
    limit_idx = len(params)
    params.append((page - 1) * page_size)
    offset_idx = len(params)

    list_query = f"""
        SELECT u.platform, u.user_id, u.username, u.name, u.phone, u.region, u.source, u.current_stage,
               u.has_property, u.is_blocked, u.created_at, u.updated_at, u.tag_id, t.name AS tag_name
        FROM ({USERS_UNION}) u
        LEFT JOIN tags t ON t.id = u.tag_id
        {where_clause}
        ORDER BY u.created_at DESC
        LIMIT ${limit_idx} OFFSET ${offset_idx}
    """

    async with database.DB_POOL.acquire() as conn:
        total = await conn.fetchval(count_query, *params[:-2])
        rows = await conn.fetch(list_query, *params)

    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/{platform}/{user_id}/tag")
async def assign_tag(platform: str, user_id: int, body: TagAssignIn):
    table = PLATFORM_TABLES.get(platform)
    if table is None:
        raise HTTPException(status_code=422, detail=f"Неизвестная платформа: {platform}")

    async with database.DB_POOL.acquire() as conn:
        if body.tag_id is not None:
            tag = await conn.fetchrow("SELECT id FROM tags WHERE id = $1", body.tag_id)
            if not tag:
                raise HTTPException(status_code=404, detail="Тег не найден")
        result = await conn.execute(
            f"UPDATE {table} SET tag_id = $1, updated_at = now() WHERE user_id = $2",
            body.tag_id, user_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"ok": True}
