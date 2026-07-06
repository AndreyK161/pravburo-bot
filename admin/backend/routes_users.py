from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import database

router = APIRouter(prefix="/api/users", tags=["users"])


class TagAssignIn(BaseModel):
    tag_id: int | None


@router.get("")
async def list_users(tag_id: int | None = None):
    query = """
        SELECT u.user_id, u.username, u.name, u.phone, u.region, u.source,
               u.created_at, u.updated_at, u.tag_id, t.name AS tag_name
        FROM users u
        LEFT JOIN tags t ON t.id = u.tag_id
    """
    params = []
    if tag_id is not None:
        query += " WHERE u.tag_id = $1"
        params.append(tag_id)
    query += " ORDER BY u.created_at DESC"

    async with database.DB_POOL.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


@router.patch("/{user_id}/tag")
async def assign_tag(user_id: int, body: TagAssignIn):
    async with database.DB_POOL.acquire() as conn:
        if body.tag_id is not None:
            tag = await conn.fetchrow("SELECT id FROM tags WHERE id = $1", body.tag_id)
            if not tag:
                raise HTTPException(status_code=404, detail="Tag not found")
        result = await conn.execute(
            "UPDATE users SET tag_id = $1, updated_at = now() WHERE user_id = $2",
            body.tag_id, user_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}
