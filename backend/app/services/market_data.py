"""
MarketDataService — collects OHLCV candles via WebSocket, persists to
TimescaleDB, and publishes updates to Redis Pub/Sub.

Designed to run as a long-lived asyncio task started from the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.connectors.bybit import BybitConnector
from app.models.candle import Candle

logger = logging.getLogger(__name__)

# How long to wait before retrying after a WebSocket disconnect
RECONNECT_DELAY_SECONDS = 5

# Module-level singleton — set during app startup
_market_data_service: MarketDataService | None = None


def get_market_data_service() -> MarketDataService:
    """Get the running MarketDataService singleton."""
    if _market_data_service is None:
        raise RuntimeError("MarketDataService not initialized")
    return _market_data_service


class MarketDataService:
    def __init__(
        self,
        connector: BybitConnector,
        session_factory: async_sessionmaker[AsyncSession],
        redis: Redis,
    ) -> None:
        self._connector = connector
        self._session_factory = session_factory
        self._redis = redis
        self._tasks: dict[str, asyncio.Task] = {}  # key: "symbol:timeframe"

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def subscribe(self, symbol: str, timeframe: str = "5m") -> None:
        """Start collecting candles for a symbol/timeframe pair."""
        key = f"{symbol}:{timeframe}"
        if key in self._tasks and not self._tasks[key].done():
            logger.info("Already subscribed to %s", key)
            return
        self._tasks[key] = asyncio.create_task(
            self._watch_loop(symbol, timeframe),
            name=f"mds:{key}",
        )
        logger.info("Subscribed to %s", key)

    def unsubscribe(self, symbol: str, timeframe: str = "5m") -> None:
        """Stop collecting candles for a symbol/timeframe pair."""
        key = f"{symbol}:{timeframe}"
        task = self._tasks.pop(key, None)
        if task and not task.done():
            task.cancel()
            logger.info("Unsubscribed from %s", key)

    async def shutdown(self) -> None:
        """Cancel all running tasks and close the connector."""
        for key, task in self._tasks.items():
            task.cancel()
            logger.info("Cancelled task %s", key)
        self._tasks.clear()
        await self._connector.close()

    def active_subscriptions(self) -> list[str]:
        """Return list of active 'symbol:timeframe' keys."""
        return [k for k, t in self._tasks.items() if not t.done()]

    # ------------------------------------------------------------------ #
    #  Backfill — fetch historical candles via REST                        #
    # ------------------------------------------------------------------ #

    async def backfill(
        self,
        symbol: str,
        timeframe: str = "5m",
        limit: int = 200,
    ) -> int:
        """
        Fetch recent historical candles via REST and upsert into DB.
        Returns the number of candles persisted.
        """
        raw = await self._connector.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not raw:
            return 0
        candles = [self._parse_candle(symbol, timeframe, c) for c in raw]
        await self._upsert_candles(candles)
        logger.info("Backfilled %d candles for %s %s", len(candles), symbol, timeframe)
        return len(candles)

    # ------------------------------------------------------------------ #
    #  Internal — watch loop with auto-reconnect                           #
    # ------------------------------------------------------------------ #

    async def _watch_loop(self, symbol: str, timeframe: str) -> None:
        """Continuously watch OHLCV, auto-reconnecting on failure."""
        key = f"{symbol}:{timeframe}"
        while True:
            try:
                logger.info("Connecting WebSocket for %s", key)
                while True:
                    raw_candles = await self._connector.watch_ohlcv(symbol, timeframe)
                    candles = [
                        self._parse_candle(symbol, timeframe, c) for c in raw_candles
                    ]
                    await self._upsert_candles(candles)
                    # Publish latest candle to Redis for real-time consumers
                    if candles:
                        latest = candles[-1]
                        await self._publish_candle(key, latest)
            except asyncio.CancelledError:
                logger.info("Watch loop cancelled for %s", key)
                return
            except Exception:
                logger.exception(
                    "WebSocket error for %s — reconnecting in %ds",
                    key,
                    RECONNECT_DELAY_SECONDS,
                )
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    # ------------------------------------------------------------------ #
    #  Internal — persistence                                              #
    # ------------------------------------------------------------------ #

    async def _upsert_candles(self, candles: list[dict[str, Any]]) -> None:
        """Upsert candles into TimescaleDB using ON CONFLICT DO UPDATE."""
        if not candles:
            return
        stmt = pg_insert(Candle).values(candles)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ts", "symbol", "timeframe"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def _publish_candle(self, channel: str, candle: dict[str, Any]) -> None:
        """Publish a candle update to Redis Pub/Sub."""
        import orjson

        payload = orjson.dumps({
            "ts": candle["ts"].isoformat(),
            "symbol": candle["symbol"],
            "timeframe": candle["timeframe"],
            "open": str(candle["open"]),
            "high": str(candle["high"]),
            "low": str(candle["low"]),
            "close": str(candle["close"]),
            "volume": str(candle["volume"]),
        })
        await self._redis.publish(f"candles:{channel}", payload)

    # ------------------------------------------------------------------ #
    #  Internal — parsing                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_candle(
        symbol: str, timeframe: str, raw: list
    ) -> dict[str, Any]:
        """
        Convert ccxt OHLCV array [ts_ms, o, h, l, c, v] to a dict
        compatible with the Candle model.
        """
        ts_ms, o, h, l, c, v = raw
        return {
            "ts": datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
            "symbol": symbol,
            "timeframe": timeframe,
            "open": Decimal(str(o)),
            "high": Decimal(str(h)),
            "low": Decimal(str(l)),
            "close": Decimal(str(c)),
            "volume": Decimal(str(v)),
        }
