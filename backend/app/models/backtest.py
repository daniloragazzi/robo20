from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import text

from app.core.database import Base


class BacktestStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"


class BacktestTradeSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    params: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[BacktestStatus] = mapped_column(
        Enum(BacktestStatus, name="backteststatus"),
        nullable=False,
        default=BacktestStatus.QUEUED,
    )
    metrics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    trades: Mapped[list[BacktestTrade]] = relationship(
        "BacktestTrade", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<BacktestRun id={self.id} symbol={self.symbol!r} status={self.status}>"


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False
    )
    entry_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_ts: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    side: Mapped[BacktestTradeSide] = mapped_column(
        Enum(BacktestTradeSide, name="backtest_trade_side"), nullable=False
    )
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)

    run: Mapped[BacktestRun] = relationship("BacktestRun", back_populates="trades")

    def __repr__(self) -> str:
        return f"<BacktestTrade id={self.id} side={self.side} pnl={self.pnl}>"
