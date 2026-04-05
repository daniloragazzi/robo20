"""
REST endpoints for candle data.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.candle import Candle

router = APIRouter(prefix="/candles", tags=["candles"])


class CandleOut(BaseModel):
    ts: datetime
    symbol: str
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    model_config = {"from_attributes": True}


@router.get("/subscriptions", response_model=list[str])
async def get_subscriptions() -> list[str]:
    """Return list of active market data subscriptions."""
    from app.services.market_data import get_market_data_service

    try:
        service = get_market_data_service()
        return service.active_subscriptions()
    except RuntimeError:
        return []


@router.get("/{symbol}", response_model=list[CandleOut])
async def get_candles(
    symbol: str,
    timeframe: str = Query("5m", description="Candle timeframe, e.g. 1m, 5m, 15m, 1h, 4h, 1d"),
    limit: int = Query(200, ge=1, le=1500, description="Max candles to return"),
    since: datetime | None = Query(None, description="Return candles after this timestamp (ISO)"),
    before: datetime | None = Query(None, description="Return candles before this timestamp (ISO) — for backward pagination"),
    db: AsyncSession = Depends(get_db),
) -> list[CandleOut]:
    """
    Get historical candles for a symbol/timeframe.
    Returns newest last (ascending ts).
    """
    # Normalize symbol: accept BTC-USDT or BTCUSDT → BTC/USDT
    normalized = symbol.upper().replace("-", "/")
    if "/" not in normalized:
        # Try common pattern: BTCUSDT → BTC/USDT
        for quote in ("USDT", "USDC", "BTC", "ETH"):
            if normalized.endswith(quote) and len(normalized) > len(quote):
                normalized = normalized[: -len(quote)] + "/" + quote
                break

    stmt = (
        select(Candle)
        .where(Candle.symbol == normalized, Candle.timeframe == timeframe)
    )
    if since is not None:
        stmt = stmt.where(Candle.ts >= since)
    if before is not None:
        stmt = stmt.where(Candle.ts < before)

    # Get newest N candles: order DESC, limit, then reverse in Python
    stmt = stmt.order_by(desc(Candle.ts)).limit(limit)

    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    rows.reverse()  # Return ascending order

    return [CandleOut.model_validate(r) for r in rows]



