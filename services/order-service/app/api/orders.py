import uuid
import grpc
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.kafka import publish
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderResponse
from app.services.risk import check_order_risk, RiskException
from app import matching_pb2
from app import matching_pb2_grpc

router = APIRouter()

def get_engine_stub():
    channel = grpc.insecure_channel(settings.matching_engine_url)
    return matching_pb2_grpc.MatchingServiceStub(channel)


@router.post("/orders", response_model=OrderResponse)
async def place_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
):
    user_id = "user_test_001"

    # step 1 — risk checks
    try:
        check_order_risk(order_data, user_id)
    except RiskException as e:
        raise HTTPException(status_code=400, detail=str(e))

    # step 2 — save to postgres as new
    order_id = str(uuid.uuid4())
    db_order = Order(
        id        = order_id,
        user_id   = user_id,
        symbol    = order_data.symbol,
        side      = order_data.side.value,
        type      = order_data.type.value,
        price     = order_data.price,
        quantity  = order_data.quantity,
        filled    = 0,
        remaining = order_data.quantity,
        status    = "new",
    )
    db.add(db_order)
    db.commit()

    # step 3 — publish order.placed event to Kafka
    # this happens BEFORE sending to the matching engine
    # so the audit log always has a record even if matching fails
    publish(
        topic = "orders.placed",
        key   = order_data.symbol,   # route by symbol for ordering
        data  = {
            "order_id":  order_id,
            "user_id":   user_id,
            "symbol":    order_data.symbol,
            "side":      order_data.side.value,
            "type":      order_data.type.value,
            "price":     order_data.price,
            "quantity":  order_data.quantity,
            "status":    "new",
        }
    )

    # step 4 — send to Go matching engine via gRPC
    try:
        stub = get_engine_stub()
        response = stub.SubmitOrder(matching_pb2.SubmitOrderRequest(
            order_id = order_id,
            user_id  = user_id,
            symbol   = order_data.symbol,
            side     = order_data.side.value,
            type     = order_data.type.value,
            price    = order_data.price or 0.0,
            quantity = order_data.quantity,
        ))
    except grpc.RpcError as e:
        db_order.status = "cancelled"
        db.commit()
        raise HTTPException(
            status_code=503,
            detail=f"matching engine unavailable: {e.details()}"
        )

    # step 5 — update postgres with match result
    db_order.status    = response.status
    db_order.filled    = response.filled
    db_order.remaining = response.remaining
    db.commit()
    db.refresh(db_order)

    # step 6 — publish trade events if any matches happened
    # each trade gets its own event so consumers can process individually
    for trade in response.trades:
        publish(
            topic = "trades.executed",
            key   = trade.symbol,
            data  = {
                "trade_id":     trade.trade_id,
                "symbol":       trade.symbol,
                "buy_order_id": trade.buy_order_id,
                "sell_order_id":trade.sell_order_id,
                "buyer_id":     trade.buyer_id,
                "seller_id":    trade.seller_id,
                "price":        trade.price,
                "quantity":     trade.quantity,
                "executed_at":  trade.executed_at,
            }
        )

    # step 7 — return the updated order
    return db_order


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    return order


@router.delete("/orders/{order_id}")
async def cancel_order(
    order_id: str,
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="order not found")

    if order.status in ("filled", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"cannot cancel order with status: {order.status}"
        )

    try:
        stub = get_engine_stub()
        stub.CancelOrder(matching_pb2.CancelOrderRequest(
            order_id = order_id,
            symbol   = order.symbol,
        ))
    except grpc.RpcError:
        pass

    order.status = "cancelled"
    db.commit()

    # publish cancellation event
    publish(
        topic = "orders.cancelled",
        key   = order.symbol,
        data  = {
            "order_id": order_id,
            "user_id":  order.user_id,
            "symbol":   order.symbol,
        }
    )

    return {"message": "order cancelled", "order_id": order_id}