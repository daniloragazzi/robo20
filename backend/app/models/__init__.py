"""
ORM models package.
Import all models here so Alembic autogenerate can detect them.
"""

from app.models.backtest import BacktestRun, BacktestTrade
from app.models.candle import Candle
from app.models.chart_indicator import ChartIndicator
from app.models.notification_settings import NotificationSetting
from app.models.order import Order, Position
from app.models.strategy import (
    Strategy,
    StrategyExecution,
    StrategyIndicator,
    StrategyStep,
)

__all__ = [
    "Candle",
    "ChartIndicator",
    "Strategy",
    "StrategyIndicator",
    "StrategyStep",
    "StrategyExecution",
    "Order",
    "Position",
    "NotificationSetting",
    "BacktestRun",
    "BacktestTrade",
]
