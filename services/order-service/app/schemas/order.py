from pydantic import BaseModel, field_validator
from typing import Optional
from enum import Enum

class OrderSide(str, Enum):
    BUY  = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT  = "limit"

# what the frontend sends when placing an order
class OrderCreate(BaseModel):
    symbol:   str
    side:     OrderSide
    type:     OrderType
    price:    Optional[float] = None
    quantity: int

    @field_validator("quantity")
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("quantity must be greater than zero")
        return v

    @field_validator("price")
    def price_must_be_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("price must be greater than zero")
        return v

    @field_validator("symbol")
    def symbol_must_be_uppercase(cls, v):
        return v.upper()

class OrderResponse(BaseModel):
    id:        str
    user_id:   str
    symbol:    str
    side:      str
    type:      str
    price:     Optional[float]
    quantity:  int
    filled:    int
    remaining: int
    status:    str

    # this tells Pydantic to read from SQLAlchemy model attributes
    # not just plain dict keys
    model_config = {"from_attributes": True}
