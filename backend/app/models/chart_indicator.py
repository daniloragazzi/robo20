"""
ChartIndicator — persisted indicator instances on the chart.
Not tied to any strategy — these are the user's chart configuration.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Integer, String, Text, Boolean, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChartIndicator(Base):
    __tablename__ = "chart_indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indicator_type: Mapped[str] = mapped_column(String(60), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    follow_chart_tf: Mapped[bool] = mapped_column(nullable=False, default=True)
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notify_telegram: Mapped[bool] = mapped_column(nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<ChartIndicator id={self.id} type={self.indicator_type!r} tf={self.timeframe}>"
