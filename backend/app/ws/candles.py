"""
WebSocket gateway for real-time candle updates.

Subscribes to Redis Pub/Sub and forwards updates to connected clients.
Auto-subscribes MarketDataService when a new symbol/timeframe is requested.
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.redis import get_redis
from app.services.market_data import get_market_data_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_symbol(symbol: str) -> str:
    """Normalize symbol: BTC-USDT or BTCUSDT → BTC/USDT."""
    normalized = symbol.upper().replace("-", "/")
    if "/" not in normalized:
        for quote in ("USDT", "USDC", "BTC", "ETH"):
            if normalized.endswith(quote) and len(normalized) > len(quote):
                normalized = normalized[: -len(quote)] + "/" + quote
                break
    return normalized


@router.websocket("/candles/{symbol}/{timeframe}")
async def candle_stream(websocket: WebSocket, symbol: str, timeframe: str) -> None:
    """
    Stream real-time candle updates via WebSocket.

    - Auto-subscribes MarketDataService if not already collecting this pair.
    - Triggers a backfill of historical data in the background.
    - Forwards Redis Pub/Sub messages to the WebSocket client.
    """
    await websocket.accept()

    normalized = _normalize_symbol(symbol)
    channel = f"candles:{normalized}:{timeframe}"

    # Ensure MarketDataService is collecting for this pair
    try:
        service = get_market_data_service()
        service.subscribe(normalized, timeframe)
        # Backfill historical data in background (idempotent upsert)
        asyncio.create_task(service.backfill(normalized, timeframe, limit=500))
    except RuntimeError:
        logger.warning("MarketDataService not available")
        await websocket.close(code=1011, reason="Market data service unavailable")
        return

    # Subscribe to Redis Pub/Sub channel
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    try:

        async def _forward_redis() -> None:
            """Listen to Redis Pub/Sub and forward messages to WebSocket."""
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    await websocket.send_text(msg["data"])

        async def _recv_ws() -> None:
            """Wait for client disconnect."""
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass

        fwd_task = asyncio.create_task(_forward_redis())
        recv_task = asyncio.create_task(_recv_ws())

        # When either task finishes, cancel the other
        done, pending = await asyncio.wait(
            [fwd_task, recv_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()

    except Exception:
        logger.exception("WebSocket error for %s", channel)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        logger.debug("WebSocket cleanup done for %s", channel)
