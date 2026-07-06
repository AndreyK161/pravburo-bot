from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import database
from routes_stats import router as stats_router
from routes_tags import router as tags_router
from routes_users import router as users_router
from routes_scenario import router as scenario_router

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db_pool()
    yield
    await database.close_db_pool()


app = FastAPI(title="Bot Pravburo Admin", lifespan=lifespan)

app.include_router(stats_router)
app.include_router(tags_router)
app.include_router(users_router)
app.include_router(scenario_router)

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
