"""
Mini App API routes — serve the webapp and provide data endpoints.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func

from bot.database.db import async_session
from bot.models.user import User
from bot.models.address_check import AddressCheck
from bot.services.gamification import get_leaderboard

router = APIRouter(prefix="/webapp")

templates = Jinja2Templates(directory="bot/webapp/templates")


@router.get("/", response_class=HTMLResponse)
async def webapp_index(request: Request):
    """Serve the Mini App HTML."""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/profile/{telegram_id}")
async def api_profile(telegram_id: int):
    """Get user profile data for Mini App."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"error": "User not found"}

        # Recent checks
        result = await session.execute(
            select(AddressCheck)
            .where(AddressCheck.user_id == user.id)
            .order_by(AddressCheck.created_at.desc())
            .limit(10)
        )
        checks = result.scalars().all()

        return {
            "user": {
                "username": user.username,
                "first_name": user.first_name,
                "level": user.level,
                "level_name": user.level_name,
                "xp": user.xp,
                "xp_to_next": user.xp_to_next_level,
                "checks_count": user.checks_count,
                "streak": user.streak_days,
            },
            "recent_checks": [
                {
                    "address": f"{c.address[:8]}...{c.address[-6:]}",
                    "chain": c.chain,
                    "risk_score": c.risk_score,
                    "risk_level": c.risk_level,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in checks
            ],
        }


@router.get("/api/leaderboard")
async def api_leaderboard():
    """Get leaderboard data for Mini App."""
    async with async_session() as session:
        return {"leaderboard": await get_leaderboard(session)}


@router.get("/api/stats")
async def api_stats():
    """Global stats for Mini App dashboard."""
    async with async_session() as session:
        total_users = await session.execute(select(func.count(User.id)))
        total_checks = await session.execute(select(func.count(AddressCheck.id)))
        risky_found = await session.execute(
            select(func.count(AddressCheck.id)).where(AddressCheck.risk_score > 70)
        )

        return {
            "total_users": total_users.scalar() or 0,
            "total_checks": total_checks.scalar() or 0,
            "risky_found": risky_found.scalar() or 0,
        }
