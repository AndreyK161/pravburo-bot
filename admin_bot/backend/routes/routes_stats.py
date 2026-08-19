from fastapi import APIRouter

import database

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/sources")
async def get_sources_stats():
    async with database.DB_POOL.acquire() as conn:
        rows = await conn.fetch("""
            SELECT COALESCE(source, 'unknown') AS source, COUNT(*) AS users_count
            FROM (
                -- utm_source разобран из ссылок вида start=<блок>_<источник>_<крео>
                -- (см. tg_bot/app/handlers.py) — если его нет (старые ссылки без
                -- разметки, например "YDX-DIRECT"), группируем по сырому source как раньше.
                SELECT COALESCE(utm_source, source) AS source FROM tg_users
                UNION ALL
                SELECT source FROM vk_users
            ) u
            GROUP BY source
            ORDER BY users_count DESC
        """)
    return [dict(row) for row in rows]
