from sqlalchemy import Column, String, Float, Integer, DateTime, Enum
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class OrderSide(str, enum.Enum):
    BUY  = "buy"
    SELL = "sell"

class OrderType(str, enum.Enum):
    MARKET = "market"
    LIMIT  = "limit"

class OrderStatus(str, enum.Enum):
    NEW       = "new"
    PARTIAL   = "partial_fill"
    FILLED    = "filled"
    CANCELLED = "cancelled"
    REJECTED  = "rejected"

class Order(Base):
    __tablename__ = "orders"

    id         = Column(String(36), primary_key=True, index=True)
    user_id    = Column(String(36), nullable=False, index=True)
    symbol     = Column(String(10), nullable=False, index=True)
    side       = Column(String(10), nullable=False)
    type       = Column(String(10), nullable=False)
    price      = Column(Float,      nullable=True)   # null for market orders
    quantity   = Column(Integer,    nullable=False)
    filled     = Column(Integer,    nullable=False, default=0)
    remaining  = Column(Integer,    nullable=False)
    status     = Column(String(20), nullable=False, default="new")

    # server_default=func.now() means PostgreSQL sets this automatically
    # you never need to pass created_at when inserting
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
