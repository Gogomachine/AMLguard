"""
FastAPI application — serves webhooks, Mini App, and API.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from bot.database.db import init_db, async_session
from bot.services.gamification import seed_achievements, seed_default_quests
from api.routes.webhook import router as webhook_router
from api.routes.webapp import router as webapp_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    async with async_session() as session:
        await seed_achievements(session)
        await seed_default_quests(session)
    yield
    # Shutdown


def create_app() -> FastAPI:
    app = FastAPI(
        title="TxPeek — AML Agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Mount static files for Mini App
    app.mount("/static", StaticFiles(directory="bot/webapp/static"), name="static")

    # Register routes
    app.include_router(webhook_router)
    app.include_router(webapp_router)

    return app
