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


class TagAssignIn(BaseModel):
    tag_id: int | None


@router.get("")
async def list_users(
    tag_id: int | None = None,
    field: str | None = None,
    value: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    conditions = []
    params = []

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

    count_query = f"SELECT COUNT(*) FROM users u {where_clause}"

    params.append(page_size)
    limit_idx = len(params)
    params.append((page - 1) * page_size)
    offset_idx = len(params)

    list_query = f"""
        SELECT u.user_id, u.username, u.name, u.phone, u.region, u.source, u.current_stage,
               u.created_at, u.updated_at, u.tag_id, t.name AS tag_name
        FROM users u
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


@router.patch("/{user_id}/tag")
async def assign_tag(user_id: int, body: TagAssignIn):
    async with database.DB_POOL.acquire() as conn:
        if body.tag_id is not None:
            tag = await conn.fetchrow("SELECT id FROM tags WHERE id = $1", body.tag_id)
            if not tag:
                raise HTTPException(status_code=404, detail="Тег не найден")
        result = await conn.execute(
            "UPDATE users SET tag_id = $1, updated_at = now() WHERE user_id = $2",
            body.tag_id, user_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"ok": True}
