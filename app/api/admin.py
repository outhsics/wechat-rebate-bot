from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LinkLog, Order, PayoutAccount, PayoutRecord, User
from app.services.wechat_mp_service import WeChatMPService

router = APIRouter(prefix="/api", tags=["admin"])
wechat_mp_service = WeChatMPService()


class MockOrderRequest(BaseModel):
    openid: str
    platform: str
    product_id: str
    order_amount: float
    commission_amount: float


class ConfirmPayoutRequest(BaseModel):
    note: str | None = None


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


@router.get("/payout-accounts")
def list_payout_accounts(db: Session = Depends(get_db)):
    rows = db.query(PayoutAccount).order_by(PayoutAccount.updated_at.desc()).limit(200).all()
    return [
        {
            "id": x.id,
            "openid": x.openid,
            "channel": x.channel,
            "account": x.account,
            "account_name": x.account_name,
            "is_active": x.is_active,
            "created_at": x.created_at,
            "updated_at": x.updated_at,
        }
        for x in rows
    ]


@router.get("/payout-records")
def list_payout_records(db: Session = Depends(get_db)):
    rows = db.query(PayoutRecord).order_by(PayoutRecord.created_at.desc()).limit(200).all()
    return [
        {
            "id": x.id,
            "order_id": x.order_id,
            "openid": x.openid,
            "amount": x.amount,
            "channel": x.channel,
            "account": x.account,
            "status": x.status,
            "note": x.note,
            "created_at": x.created_at,
            "confirmed_at": x.confirmed_at,
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


@router.post("/orders/{order_id}/confirm-payout")
def confirm_payout(order_id: str, payload: ConfirmPayoutRequest, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="order_not_found")

    existing = db.query(PayoutRecord).filter(PayoutRecord.order_id == order_id).first()
    if existing:
        return {
            "ok": True,
            "already_confirmed": True,
            "payout_record_id": existing.id,
            "notify_sent": False,
            "notify_result": "skipped_already_confirmed",
        }

    payout_account = (
        db.query(PayoutAccount)
        .filter(PayoutAccount.openid == order.raw_openid, PayoutAccount.is_active == 1)
        .first()
    )
    if not payout_account:
        raise HTTPException(status_code=400, detail="payout_account_not_bound")

    record = PayoutRecord(
        id=f"pay_{uuid4().hex[:18]}",
        order_id=order.id,
        user_id=order.user_id,
        openid=order.raw_openid,
        amount=order.rebate_amount,
        channel=payout_account.channel,
        account=payout_account.account,
        status="confirmed",
        note=payload.note,
        confirmed_at=datetime.utcnow(),
    )
    order.status = "paid_out"
    db.add(record)
    db.commit()

    notify_text = (
        "返利已确认发放：\n"
        f"订单号：{order.id}\n"
        f"返利金额：¥{order.rebate_amount}\n"
        f"收款渠道：{payout_account.channel}\n"
        f"收款账号：{payout_account.account}\n"
        "如有疑问请回复客服。"
    )
    notify_sent, notify_result = wechat_mp_service.send_text(order.raw_openid, notify_text)

    return {
        "ok": True,
        "payout_record_id": record.id,
        "notify_sent": notify_sent,
        "notify_result": notify_result,
    }
