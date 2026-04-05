from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.strategy import StrategyExecution


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LIMIT = "STOP_LIMIT"
    STOP_MARKET = "STOP_MARKET"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class PositionSide(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class PositionStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_execution_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("strategy_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    exchange: Mapped[str] = mapped_column(String(30), nullable=False, default="bybit")
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[OrderSide] = mapped_column(
        Enum(OrderSide, name="orderside"), nullable=False
    )
    order_type: Mapped[OrderType] = mapped_column(
        Enum(OrderType, name="ordertype"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    stop: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    target: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    # Partial exits: JSON-serialized list of {qty, target} dicts stored as text
    partial_exits: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="orderstatus"),
        nullable=False,
        default=OrderStatus.PENDING,
    )
    exchange_order_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fill_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    fill_qty: Mapped[Decimal | None] = mapped_column(Numeric(30, 8), nullable=True)
    fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    filled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    strategy_execution: Mapped[StrategyExecution | None] = relationship(  # noqa: F821
        "StrategyExecution"
    )

    def __repr__(self) -> str:
        return (
            f"<Order id={self.id} {self.side} {self.symbol} "
            f"qty={self.qty} status={self.status}>"
        )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(30), nullable=False, default="bybit")
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[PositionSide] = mapped_column(
        Enum(PositionSide, name="positionside"), nullable=False
    )
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)
    stop: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    target: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    pnl_open: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    status: Mapped[PositionStatus] = mapped_column(
        Enum(PositionStatus, name="positionstatus"),
        nullable=False,
        default=PositionStatus.OPEN,
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<Position id={self.id} {self.side} {self.symbol} "
            f"qty={self.qty} status={self.status}>"
        )
