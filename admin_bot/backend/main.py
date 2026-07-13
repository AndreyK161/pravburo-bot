import asyncio
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import bot_client
import database
from routes.routes_auth import router as auth_router, require_auth, require_role
from routes.routes_stats import router as stats_router
from routes.routes_tags import router as tags_router
from routes.routes_users import router as users_router
from routes.routes_scenario import router as scenario_router
from routes.routes_scenario_graph import router as scenario_graph_router
from routes.routes_broadcast import router as broadcast_router, check_due_broadcasts

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Отдельного воркера/Celery/Redis под отложенные рассылки нет — проверяем
# наступившие рассылки прямо в процессе админки на этом же event loop.
SCHEDULER_INTERVAL_SECONDS = 20


async def _scheduler_loop() -> None:
    while True:
        try:
            await check_due_broadcasts()
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db_pool()
    await bot_client.init_bot()
    scheduler_task = asyncio.create_task(_scheduler_loop())
    yield
    scheduler_task.cancel()
    await bot_client.close_bot()
    await database.close_db_pool()


app = FastAPI(title="Bot Pravburo Admin", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(stats_router, dependencies=[Depends(require_auth)])
app.include_router(tags_router, dependencies=[Depends(require_auth)])
app.include_router(users_router, dependencies=[Depends(require_auth)])
app.include_router(scenario_router, dependencies=[Depends(require_role("admin"))])
app.include_router(scenario_graph_router, dependencies=[Depends(require_auth)])
app.include_router(broadcast_router, dependencies=[Depends(require_auth)])

@app.get("/login")
async def login_page():
    return FileResponse(FRONTEND_DIR / "login.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
