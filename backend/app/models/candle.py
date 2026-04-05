from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Candle(Base):
    """
    Tabela de séries temporais OHLCV.
    Gerenciada como hypertable pelo TimescaleDB.
    A criação da hypertable é feita via migração Alembic raw SQL.
    """

    __tablename__ = "candles"

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(5), primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)

    __table_args__ = (
        Index("ix_candles_symbol_tf_ts", "symbol", "timeframe", text("ts DESC")),
    )

    def __repr__(self) -> str:
        return f"<Candle {self.symbol} {self.timeframe} {self.ts} C={self.close}>"
