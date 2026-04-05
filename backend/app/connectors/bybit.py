"""
BybitConnector — concrete exchange connector using ccxt (sync REST)
and ccxt.pro (async WebSocket) for Bybit.

Public data (OHLCV) does NOT require API keys.
Private data (orders, balance) requires keys — configured in Settings.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import ccxt.pro as ccxtpro

from app.core.config import settings

logger = logging.getLogger(__name__)


class BybitConnector:
    exchange_id: str = "bybit"

    def __init__(self) -> None:
        config: dict[str, Any] = {
            "enableRateLimit": True,
            "options": {"defaultType": "linear"},
        }
        if settings.bybit_api_key:
            config["apiKey"] = settings.bybit_api_key
            config["secret"] = settings.bybit_api_secret
            # Only use testnet/sandbox for authenticated (private) endpoints
            if settings.bybit_testnet:
                config["sandbox"] = True

        # For public data (OHLCV), we always use mainnet — it's free,
        # has more liquidity, and doesn't require API keys.
        # Sandbox mode is only relevant for order placement (Sprint 7).
        self._exchange: ccxtpro.bybit = ccxtpro.bybit(config)

    # ------------------------------------------------------------------ #
    #  Public — Market Data                                                #
    # ------------------------------------------------------------------ #

    async def watch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "5m",
    ) -> list[list]:
        """
        Watch OHLCV candles via WebSocket.
        Returns a list of candle arrays: [[ts_ms, o, h, l, c, v], ...]
        Each call blocks until new data arrives.
        """
        return await self._exchange.watch_ohlcv(symbol, timeframe)

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "5m",
        since: int | None = None,
        limit: int = 200,
    ) -> list[list]:
        """
        Fetch historical OHLCV candles via REST.
        Returns [[ts_ms, o, h, l, c, v], ...]
        """
        return await self._exchange.fetch_ohlcv(
            symbol, timeframe, since=since, limit=limit
        )

    async def fetch_markets(self) -> dict[str, Any]:
        """Load and return all markets info."""
        return await self._exchange.load_markets()

    # ------------------------------------------------------------------ #
    #  Private — Orders (Sprint 7)                                         #
    # ------------------------------------------------------------------ #

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        qty: float,
        price: float | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._exchange.create_order(
            symbol, order_type, side, qty, price, params or {}
        )

    async def cancel_order(
        self, order_id: str, symbol: str
    ) -> dict[str, Any]:
        return await self._exchange.cancel_order(order_id, symbol)

    async def fetch_order(
        self, order_id: str, symbol: str
    ) -> dict[str, Any]:
        return await self._exchange.fetch_order(order_id, symbol)

    async def fetch_balance(self) -> dict[str, Any]:
        return await self._exchange.fetch_balance()

    async def fetch_positions(self) -> list[dict[str, Any]]:
        return await self._exchange.fetch_positions()

    async def watch_orders(self, symbol: str) -> None:
        """Stream private order updates — Sprint 7."""
        raise NotImplementedError("watch_orders will be implemented in Sprint 7")

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    async def close(self) -> None:
        """Gracefully close all WebSocket connections."""
        try:
            await self._exchange.close()
        except Exception:
            logger.exception("Error closing Bybit exchange connection")
