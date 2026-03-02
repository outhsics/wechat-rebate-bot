from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LinkLog, Order, User

router = APIRouter(prefix="/api", tags=["admin"])


class MockOrderRequest(BaseModel):
    openid: str
    platform: str
    product_id: str
    order_amount: float
    commission_amount: float


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    rows = db.query(User).order_by(User.created_at.desc()).limit(100).all()
    return [
        {"id": x.id, "openid": x.openid, "nickname": x.nickname, "created_at": x.created_at}
        for x in rows
    ]


@router.get("/link-logs")
def list_link_logs(db: Session = Depends(get_db)):
    rows = db.query(LinkLog).order_by(LinkLog.created_at.desc()).limit(200).all()
    return [
        {
            "id": x.id,
            "raw_openid": x.raw_openid,
            "platform": x.platform,
            "product_id": x.product_id,
            "quote_price": x.quote_price,
            "quote_commission": x.quote_commission,
            "quote_rebate": x.quote_rebate,
            "created_at": x.created_at,
        }
        for x in rows
    ]


@router.get("/orders")
def list_orders(db: Session = Depends(get_db)):
    rows = db.query(Order).order_by(Order.created_at.desc()).limit(200).all()
    return [
        {
            "id": x.id,
            "raw_openid": x.raw_openid,
            "platform": x.platform,
            "product_id": x.product_id,
            "order_amount": x.order_amount,
            "commission_amount": x.commission_amount,
            "rebate_amount": x.rebate_amount,
            "status": x.status,
            "created_at": x.created_at,
            "updated_at": x.updated_at,
        }
        for x in rows
    ]


@router.post("/orders/mock-confirm")
def mock_confirm_order(payload: MockOrderRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.openid == payload.openid).first()
    order = Order(
        id=f"mock_{uuid4().hex[:18]}",
        user_id=user.id if user else None,
        raw_openid=payload.openid,
        platform=payload.platform,
        product_id=payload.product_id,
        order_amount=payload.order_amount,
        commission_amount=payload.commission_amount,
        rebate_amount=round(payload.commission_amount * 0.7, 2),
        status="settled",
        created_at=datetime.utcnow(),
    )
    db.add(order)
    db.commit()
    return {"ok": True, "order_id": order.id}
