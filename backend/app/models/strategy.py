from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class StrategyMode(str, enum.Enum):
    SINAL_APENAS = "SINAL_APENAS"
    SEMI_AUTO = "SEMI_AUTO"
    TOTALMENTE_AUTO = "TOTALMENTE_AUTO"


class ExecutionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[StrategyMode] = mapped_column(
        Enum(StrategyMode, name="strategymode"),
        nullable=False,
        default=StrategyMode.SINAL_APENAS,
    )
    risk_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    indicators: Mapped[list[StrategyIndicator]] = relationship(
        "StrategyIndicator", back_populates="strategy", cascade="all, delete-orphan"
    )
    steps: Mapped[list[StrategyStep]] = relationship(
        "StrategyStep", back_populates="strategy", cascade="all, delete-orphan"
    )
    executions: Mapped[list[StrategyExecution]] = relationship(
        "StrategyExecution", back_populates="strategy"
    )

    def __repr__(self) -> str:
        return f"<Strategy id={self.id} name={self.name!r} mode={self.mode}>"


class StrategyIndicator(Base):
    __tablename__ = "strategy_indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False
    )
    indicator_type: Mapped[str] = mapped_column(String(60), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notify_telegram: Mapped[bool] = mapped_column(nullable=False, default=False)

    strategy: Mapped[Strategy] = relationship("Strategy", back_populates="indicators")

    def __repr__(self) -> str:
        return f"<StrategyIndicator id={self.id} type={self.indicator_type!r}>"


class StrategyStep(Base):
    __tablename__ = "strategy_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    indicator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("strategy_indicators.id", ondelete="SET NULL"),
        nullable=True,
    )
    condition_type: Mapped[str] = mapped_column(String(60), nullable=False)
    condition_value: Mapped[str | None] = mapped_column(String(120), nullable=True)
    condition_tree: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    strategy: Mapped[Strategy] = relationship("Strategy", back_populates="steps")
    indicator: Mapped[StrategyIndicator | None] = relationship("StrategyIndicator")

    def __repr__(self) -> str:
        return f"<StrategyStep id={self.id} index={self.step_index}>"


class StrategyExecution(Base):
    __tablename__ = "strategy_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("strategies.id", ondelete="RESTRICT"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, name="executionstatus"),
        nullable=False,
        default=ExecutionStatus.ACTIVE,
    )
    current_state: Mapped[str | None] = mapped_column(String(60), nullable=True)
    context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_transition: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    strategy: Mapped[Strategy] = relationship("Strategy", back_populates="executions")

    def __repr__(self) -> str:
        return f"<StrategyExecution id={self.id} symbol={self.symbol!r} status={self.status}>"
