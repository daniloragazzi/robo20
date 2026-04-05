"""Tests for MarketDataService — candle parsing and upsert logic."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.market_data import MarketDataService


class TestParseCandle:
    """Test the static _parse_candle method."""

    def test_basic_parse(self) -> None:
        raw = [1700000000000, 36000.5, 36100.0, 35900.0, 36050.25, 123.456]
        result = MarketDataService._parse_candle("BTC/USDT", "5m", raw)

        assert result["symbol"] == "BTC/USDT"
        assert result["timeframe"] == "5m"
        assert result["ts"] == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
        assert result["open"] == Decimal("36000.5")
        assert result["high"] == Decimal("36100.0")
        assert result["low"] == Decimal("35900.0")
        assert result["close"] == Decimal("36050.25")
        assert result["volume"] == Decimal("123.456")

    def test_integer_values(self) -> None:
        raw = [1700000000000, 100, 200, 50, 150, 1000]
        result = MarketDataService._parse_candle("ETH/USDT", "1h", raw)

        assert result["open"] == Decimal("100")
        assert result["volume"] == Decimal("1000")

    def test_small_decimals(self) -> None:
        raw = [1700000000000, 0.00001234, 0.00001300, 0.00001200, 0.00001250, 9999999.99]
        result = MarketDataService._parse_candle("PEPE/USDT", "15m", raw)

        assert result["open"] == Decimal("0.00001234")
        assert result["volume"] == Decimal("9999999.99")

    def test_timestamp_conversion(self) -> None:
        # 2026-01-01 00:00:00 UTC
        ts_ms = 1767225600000
        raw = [ts_ms, 1, 2, 0.5, 1.5, 100]
        result = MarketDataService._parse_candle("BTC/USDT", "1d", raw)

        assert result["ts"].year == 2026
        assert result["ts"].month == 1
        assert result["ts"].day == 1
        assert result["ts"].tzinfo == timezone.utc
