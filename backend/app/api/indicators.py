"""
REST endpoints for indicators — list available, compute values, manage chart instances.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.indicators.registry import compute_indicator, list_indicators
from app.models.candle import Candle
from app.models.chart_indicator import ChartIndicator

router = APIRouter(prefix="/indicators", tags=["indicators"])


# ------------------------------------------------------------------ #
#  Schemas                                                             #
# ------------------------------------------------------------------ #


class IndicatorInfo(BaseModel):
    name: str
    display_name: str
    params_schema: dict[str, Any]


class ComputeRequest(BaseModel):
    indicator: str
    symbol: str
    timeframe: str = "5m"
    params: dict[str, Any] = {}
    limit: int = 500


class IndicatorDataPoint(BaseModel):
    ts: datetime
    values: dict[str, float | str | None]


class ChartIndicatorIn(BaseModel):
    indicator_type: str
    params: dict[str, Any] = {}
    timeframe: str = "5m"
    follow_chart_tf: bool = True
    label: str | None = None
    notify_telegram: bool = False


class ChartIndicatorOut(BaseModel):
    id: int
    indicator_type: str
    params: dict[str, Any]
    timeframe: str
    follow_chart_tf: bool
    label: str | None
    notify_telegram: bool

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------ #
#  List available indicators                                           #
# ------------------------------------------------------------------ #


@router.get("/", response_model=list[IndicatorInfo])
async def get_available_indicators() -> list[IndicatorInfo]:
    """Return metadata for all registered indicator plugins."""
    return [IndicatorInfo(**info) for info in list_indicators()]


# ------------------------------------------------------------------ #
#  Compute indicator values                                            #
# ------------------------------------------------------------------ #


def _normalize_symbol(symbol: str) -> str:
    normalized = symbol.upper().replace("-", "/")
    if "/" not in normalized:
        for quote in ("USDT", "USDC", "BTC", "ETH"):
            if normalized.endswith(quote) and len(normalized) > len(quote):
                normalized = normalized[: -len(quote)] + "/" + quote
                break
    return normalized


@router.post("/compute", response_model=list[IndicatorDataPoint])
async def compute(
    req: ComputeRequest,
    db: AsyncSession = Depends(get_db),
) -> list[IndicatorDataPoint]:
    """
    Compute an indicator on historical candles and return the resulting values.
    Only returns rows that have at least one non-null indicator value.
    If candles for the requested timeframe are missing, auto-backfills from exchange.
    """
    normalized = _normalize_symbol(req.symbol)

    # Fetch candles from DB
    from sqlalchemy import desc

    stmt = (
        select(Candle)
        .where(Candle.symbol == normalized, Candle.timeframe == req.timeframe)
        .order_by(desc(Candle.ts))
        .limit(req.limit)
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    # Auto-backfill if no candles exist for this timeframe
    if not rows:
        try:
            from app.services.market_data import get_market_data_service

            mds = get_market_data_service()
            count = await mds.backfill(normalized, req.timeframe, limit=req.limit)
            if count:
                mds.subscribe(normalized, req.timeframe)
                result = await db.execute(stmt)
                rows = list(result.scalars().all())
        except RuntimeError:
            pass  # MarketDataService not running
    rows.reverse()

    if not rows:
        raise HTTPException(404, "No candle data found for the given symbol/timeframe")

    # Build DataFrame
    df = pd.DataFrame(
        [
            {
                "ts": r.ts,
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "volume": float(r.volume),
            }
            for r in rows
        ]
    )

    # Compute indicator
    try:
        result_df = compute_indicator(req.indicator, df, req.params)
    except KeyError:
        raise HTTPException(400, f"Unknown indicator: {req.indicator}")

    # Extract only new columns (indicator output)
    base_cols = {"ts", "open", "high", "low", "close", "volume"}
    indicator_cols = [c for c in result_df.columns if c not in base_cols]

    if not indicator_cols:
        return []

    # Build response — only rows with at least one non-null indicator value
    points: list[IndicatorDataPoint] = []
    for _, row in result_df.iterrows():
        vals: dict[str, float | str | None] = {}
        any_value = False
        for col in indicator_cols:
            v = row[col]
            try:
                is_null = v is None or pd.isna(v)
            except (ValueError, TypeError):
                is_null = False
            if is_null:
                vals[col] = None
            elif isinstance(v, str):
                vals[col] = v
                any_value = True
            else:
                try:
                    vals[col] = float(v)
                    any_value = True
                except (ValueError, TypeError):
                    vals[col] = str(v)
                    any_value = True
        if any_value:
            points.append(IndicatorDataPoint(ts=row["ts"], values=vals))

    return points


# ------------------------------------------------------------------ #
#  Chart indicator instances — CRUD (persisted per-chart config)       #
# ------------------------------------------------------------------ #


@router.get("/chart", response_model=list[ChartIndicatorOut])
async def get_chart_indicators(
    db: AsyncSession = Depends(get_db),
) -> list[ChartIndicatorOut]:
    """Return all persisted chart indicator instances."""
    stmt = select(ChartIndicator)
    result = await db.execute(stmt)
    return [ChartIndicatorOut.model_validate(r) for r in result.scalars().all()]


@router.post("/chart", response_model=ChartIndicatorOut, status_code=201)
async def add_chart_indicator(
    body: ChartIndicatorIn,
    db: AsyncSession = Depends(get_db),
) -> ChartIndicatorOut:
    """Add an indicator instance to the chart and persist it."""
    # Validate indicator exists
    try:
        from app.indicators.registry import get_indicator
        get_indicator(body.indicator_type)
    except KeyError:
        raise HTTPException(400, f"Unknown indicator: {body.indicator_type}")

    ind = ChartIndicator(
        indicator_type=body.indicator_type,
        params=body.params,
        timeframe=body.timeframe,
        follow_chart_tf=body.follow_chart_tf,
        label=body.label,
        notify_telegram=body.notify_telegram,
    )
    db.add(ind)
    await db.commit()
    await db.refresh(ind)
    return ChartIndicatorOut.model_validate(ind)


@router.delete("/chart/{indicator_id}", status_code=204)
async def remove_chart_indicator(
    indicator_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a persisted chart indicator instance."""
    stmt = delete(ChartIndicator).where(ChartIndicator.id == indicator_id)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(404, "Indicator instance not found")
    await db.commit()
