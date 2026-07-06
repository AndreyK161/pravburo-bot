from fastapi import APIRouter

import database

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/sources")
async def get_sources_stats():
    async with database.DB_POOL.acquire() as conn:
        rows = await conn.fetch("""
            SELECT COALESCE(source, 'unknown') AS source, COUNT(*) AS users_count
            FROM users
            GROUP BY source
            ORDER BY users_count DESC
        """)
    return [dict(row) for row in rows]
