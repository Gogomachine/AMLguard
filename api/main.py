"""
FastAPI application — serves Telegram webhook.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from bot.database.db import init_db
from api.routes.webhook import router as webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown


def create_app() -> FastAPI:
    app = FastAPI(
        title="TxPeek — AML Agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(webhook_router)

    return app
