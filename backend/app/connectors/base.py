"""
ExchangeConnector — Protocol that all exchange integrations must satisfy.
Concrete implementations (e.g. BybitConnector) live as separate modules in
this package and are registered at startup.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ExchangeConnector(Protocol):
    exchange_id: str  # e.g. "bybit"

    # ------------------------------------------------------------------ #
    #  REST                                                                #
    # ------------------------------------------------------------------ #

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        qty: float,
        price: float | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def cancel_order(
        self, order_id: str, symbol: str
    ) -> dict[str, Any]: ...

    async def fetch_order(
        self, order_id: str, symbol: str
    ) -> dict[str, Any]: ...

    async def fetch_balance(self) -> dict[str, Any]: ...

    async def fetch_positions(self) -> list[dict[str, Any]]: ...

    # ------------------------------------------------------------------ #
    #  WebSocket streaming                                                 #
    # ------------------------------------------------------------------ #

    async def watch_orders(self, symbol: str) -> None:
        """Stream order updates. Should publish events to Redis pub/sub."""
        ...

    async def watch_ohlcv(self, symbol: str, timeframe: str) -> None:
        """Stream OHLCV candles. Should persist to TimescaleDB."""
        ...

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    async def close(self) -> None: ...
