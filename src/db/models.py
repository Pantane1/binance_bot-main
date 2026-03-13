from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Position(Base):
    """Represents an open or closed trading position."""

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    is_futures = Column(Boolean, default=False, nullable=False)
    direction = Column(String(8), nullable=False)  # 'LONG' or 'SHORT'
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)
    size = Column(Float, nullable=False)
    leverage = Column(Integer, default=1, nullable=False)
    opened_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    status = Column(String(16), default="OPEN", nullable=False)  # OPEN / CLOSED
    pnl = Column(Float, nullable=True)

    trades = relationship("Trade", back_populates="position")

    __table_args__ = (
        Index("idx_positions_symbol_status", "symbol", "status"),
    )


class Trade(Base):
    """Represents an individual fill/order execution."""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)

    symbol = Column(String, nullable=False, index=True)
    side = Column(String(8), nullable=False)  # BUY / SELL
    price = Column(Float, nullable=False)
    qty = Column(Float, nullable=False)
    notional = Column(Float, nullable=True)
    fee = Column(Float, nullable=True)
    is_futures = Column(Boolean, default=False, nullable=False)
    exchange_order_id = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    position = relationship("Position", back_populates="trades")


