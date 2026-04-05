from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NotificationSetting(Base):
    """
    Configurações de notificação por canal.
    Para o Telegram: armazena bot_token e chat_id nesta tabela (NT-04).
    Gerenciado pela tela de Settings do frontend.
    NÃO usar variáveis de ambiente para credenciais do Telegram.
    """

    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(
        String(30), nullable=False, unique=True
    )  # e.g. "telegram"
    # For Telegram: the bot token obtained from @BotFather
    token: Mapped[str | None] = mapped_column(Text, nullable=True)
    # For Telegram: the target chat_id (user or group)
    target: Mapped[str | None] = mapped_column(String(120), nullable=True)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<NotificationSetting channel={self.channel!r} enabled={self.enabled}>"
