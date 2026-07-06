from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

import bot_client
import database
from routes.routes_auth import router as auth_router, require_auth
from routes.routes_stats import router as stats_router
from routes.routes_tags import router as tags_router
from routes.routes_users import router as users_router
from routes.routes_scenario import router as scenario_router
from routes.routes_broadcast import router as broadcast_router

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db_pool()
    await bot_client.init_bot()
    yield
    await bot_client.close_bot()
    await database.close_db_pool()


app = FastAPI(title="Bot Pravburo Admin", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(stats_router, dependencies=[Depends(require_auth)])
app.include_router(tags_router, dependencies=[Depends(require_auth)])
app.include_router(users_router, dependencies=[Depends(require_auth)])
app.include_router(scenario_router, dependencies=[Depends(require_auth)])
app.include_router(broadcast_router, dependencies=[Depends(require_auth)])

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
