"""
Telegram webhook endpoint.
"""

from fastapi import APIRouter, Request, Response

router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(request: Request) -> Response:
    """Process Telegram webhook updates."""
    # The bot application is stored in app state by main.py
    bot_app = request.app.state.bot_app

    update_data = await request.json()

    from telegram import Update
    update = Update.de_json(update_data, bot_app.bot)
    await bot_app.process_update(update)

    return Response(status_code=200)
