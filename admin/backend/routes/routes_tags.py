from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import database

router = APIRouter(prefix="/api/tags", tags=["tags"])


class TagIn(BaseModel):
    name: str


@router.get("")
async def list_tags():
    async with database.DB_POOL.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, created_at FROM tags ORDER BY name")
    return [dict(row) for row in rows]


@router.post("")
async def create_tag(tag: TagIn):
    name = tag.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Tag name must not be empty")
    async with database.DB_POOL.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM tags WHERE name = $1", name)
        if existing:
            raise HTTPException(status_code=409, detail="Tag with this name already exists")
        row = await conn.fetchrow(
            "INSERT INTO tags (name) VALUES ($1) RETURNING id, name, created_at", name
        )
    return dict(row)


@router.delete("/{tag_id}")
async def delete_tag(tag_id: int):
    async with database.DB_POOL.acquire() as conn:
        result = await conn.execute("DELETE FROM tags WHERE id = $1", tag_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"ok": True}
