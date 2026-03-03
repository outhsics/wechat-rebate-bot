from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import (
    LinkLog,
    Order,
    PayoutAccount,
    PayoutRecord,
    RiskBlocklist,
    User,
    WithdrawalRequest,
)
from app.services.wechat_mp_service import WeChatMPService

settings = get_settings()


def require_admin_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not x_api_key or x_api_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="unauthorized")


router = APIRouter(
    prefix="/api",
    tags=["admin"],
    dependencies=[Depends(require_admin_api_key)],
)
wechat_mp_service = WeChatMPService()


class MockOrderRequest(BaseModel):
    openid: str
    platform: str
    product_id: str
    order_amount: float
    commission_amount: float


class ConfirmPayoutRequest(BaseModel):
    note: str | None = None


class OrderCallbackRequest(BaseModel):
    order_id: str
    openid: str
    platform: str
    product_id: str
    order_amount: float
    commission_amount: float
    status: str = "settled"


class WithdrawalActionRequest(BaseModel):
    note: str | None = None


class UpsertBlocklistRequest(BaseModel):
    openid: str
    reason: str | None = None
    is_active: int = 1


def _get_or_create_user(db: Session, openid: str) -> User:
    user = db.query(User).filter(User.openid == openid).first()
    if user:
        return user
    user = User(openid=openid)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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


@router.post("/orders/callback")
def sync_order_callback(payload: OrderCallbackRequest, db: Session = Depends(get_db)):
    user = _get_or_create_user(db, payload.openid)
    status = payload.status.strip().lower()
    rebate_amount = round(payload.commission_amount * settings.rebate_rate, 2)

    order = db.query(Order).filter(Order.id == payload.order_id).first()
    if order:
        order.user_id = user.id
        order.raw_openid = payload.openid
        order.platform = payload.platform
        order.product_id = payload.product_id
        order.order_amount = payload.order_amount
        order.commission_amount = payload.commission_amount
        order.rebate_amount = rebate_amount
        order.status = status
        db.commit()
        return {"ok": True, "updated": True, "order_id": order.id, "status": order.status}

    order = Order(
        id=payload.order_id,
        user_id=user.id,
        raw_openid=payload.openid,
        platform=payload.platform,
        product_id=payload.product_id,
        order_amount=payload.order_amount,
        commission_amount=payload.commission_amount,
        rebate_amount=rebate_amount,
        status=status,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(order)
    db.commit()
    return {"ok": True, "created": True, "order_id": order.id, "status": order.status}


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


@router.get("/withdraw-requests")
def list_withdraw_requests(db: Session = Depends(get_db)):
    rows = db.query(WithdrawalRequest).order_by(WithdrawalRequest.created_at.desc()).limit(200).all()
    return [
        {
            "id": x.id,
            "openid": x.openid,
            "amount": x.amount,
            "status": x.status,
            "note": x.note,
            "created_at": x.created_at,
            "updated_at": x.updated_at,
        }
        for x in rows
    ]


@router.post("/withdraw-requests/{request_id}/approve")
def approve_withdraw_request(
    request_id: str,
    payload: WithdrawalActionRequest,
    db: Session = Depends(get_db),
):
    row = db.query(WithdrawalRequest).filter(WithdrawalRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="withdraw_request_not_found")
    if row.status not in {"pending", "approved"}:
        raise HTTPException(status_code=400, detail=f"invalid_status:{row.status}")

    row.status = "approved"
    row.note = payload.note or "approved_by_admin"
    db.commit()
    return {"ok": True, "request_id": row.id, "status": row.status}


@router.post("/withdraw-requests/{request_id}/reject")
def reject_withdraw_request(
    request_id: str,
    payload: WithdrawalActionRequest,
    db: Session = Depends(get_db),
):
    row = db.query(WithdrawalRequest).filter(WithdrawalRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="withdraw_request_not_found")
    if row.status in {"paid", "rejected"}:
        raise HTTPException(status_code=400, detail=f"invalid_status:{row.status}")

    row.status = "rejected"
    row.note = payload.note or "rejected_by_admin"
    db.commit()
    return {"ok": True, "request_id": row.id, "status": row.status}


@router.post("/withdraw-requests/{request_id}/mark-paid")
def mark_withdraw_request_paid(
    request_id: str,
    payload: WithdrawalActionRequest,
    db: Session = Depends(get_db),
):
    row = db.query(WithdrawalRequest).filter(WithdrawalRequest.id == request_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="withdraw_request_not_found")
    if row.status not in {"pending", "approved"}:
        raise HTTPException(status_code=400, detail=f"invalid_status:{row.status}")

    existing = (
        db.query(PayoutRecord)
        .filter(PayoutRecord.order_id == f"withdraw:{request_id}")
        .first()
    )
    if existing:
        row.status = "paid"
        db.commit()
        return {"ok": True, "already_paid": True, "payout_record_id": existing.id}

    payout_account = (
        db.query(PayoutAccount)
        .filter(PayoutAccount.openid == row.openid, PayoutAccount.is_active == 1)
        .first()
    )
    if not payout_account:
        raise HTTPException(status_code=400, detail="payout_account_not_bound")

    payout_record = PayoutRecord(
        id=f"pay_{uuid4().hex[:18]}",
        order_id=f"withdraw:{request_id}",
        user_id=row.user_id,
        openid=row.openid,
        amount=row.amount,
        channel=payout_account.channel,
        account=payout_account.account,
        status="paid",
        note=payload.note or "withdraw_paid",
        confirmed_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(payout_record)
    row.status = "paid"
    row.note = payload.note or row.note
    db.commit()

    notify_text = (
        "提现已发放：\n"
        f"工单号：{row.id}\n"
        f"金额：¥{row.amount}\n"
        f"收款渠道：{payout_account.channel}\n"
        f"收款账号：{payout_account.account}"
    )
    notify_sent, notify_result = wechat_mp_service.send_text(row.openid, notify_text)
    return {
        "ok": True,
        "request_id": row.id,
        "status": row.status,
        "payout_record_id": payout_record.id,
        "notify_sent": notify_sent,
        "notify_result": notify_result,
    }


@router.get("/risk-blocklist")
def list_risk_blocklist(db: Session = Depends(get_db)):
    rows = db.query(RiskBlocklist).order_by(RiskBlocklist.updated_at.desc()).limit(200).all()
    return [
        {
            "id": x.id,
            "openid": x.openid,
            "reason": x.reason,
            "is_active": x.is_active,
            "created_at": x.created_at,
            "updated_at": x.updated_at,
        }
        for x in rows
    ]


@router.post("/risk-blocklist/upsert")
def upsert_risk_blocklist(payload: UpsertBlocklistRequest, db: Session = Depends(get_db)):
    row = db.query(RiskBlocklist).filter(RiskBlocklist.openid == payload.openid).first()
    if row:
        row.reason = payload.reason
        row.is_active = payload.is_active
    else:
        row = RiskBlocklist(
            openid=payload.openid,
            reason=payload.reason,
            is_active=payload.is_active,
        )
        db.add(row)
    db.commit()
    return {"ok": True, "openid": row.openid, "is_active": row.is_active}


@router.post("/orders/mock-confirm")
def mock_confirm_order(payload: MockOrderRequest, db: Session = Depends(get_db)):
    user = _get_or_create_user(db, payload.openid)
    order = Order(
        id=f"mock_{uuid4().hex[:18]}",
        user_id=user.id,
        raw_openid=payload.openid,
        platform=payload.platform,
        product_id=payload.product_id,
        order_amount=payload.order_amount,
        commission_amount=payload.commission_amount,
        rebate_amount=round(payload.commission_amount * settings.rebate_rate, 2),
        status="settled",
        created_at=datetime.now(UTC).replace(tzinfo=None),
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
        confirmed_at=datetime.now(UTC).replace(tzinfo=None),
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


@router.get("/reports/reconciliation")
def get_reconciliation_report(
    day: str = Query(default="", description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    if day:
        try:
            start = datetime.strptime(day, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_day_format_use_yyyy_mm_dd") from exc
    else:
        now = datetime.now(UTC).replace(tzinfo=None)
        start = datetime(now.year, now.month, now.day)
    end = start + timedelta(days=1)

    order_count = db.query(func.count(Order.id)).filter(Order.created_at >= start, Order.created_at < end).scalar()
    order_amount_total = (
        db.query(func.sum(Order.order_amount)).filter(Order.created_at >= start, Order.created_at < end).scalar()
        or 0
    )
    commission_total = (
        db.query(func.sum(Order.commission_amount))
        .filter(Order.created_at >= start, Order.created_at < end)
        .scalar()
        or 0
    )
    settled_rebate_total = (
        db.query(func.sum(Order.rebate_amount))
        .filter(Order.created_at >= start, Order.created_at < end, Order.status.in_(["settled", "paid_out"]))
        .scalar()
        or 0
    )
    payout_total = (
        db.query(func.sum(PayoutRecord.amount))
        .filter(PayoutRecord.created_at >= start, PayoutRecord.created_at < end)
        .scalar()
        or 0
    )
    pending_withdraw_total = (
        db.query(func.sum(WithdrawalRequest.amount))
        .filter(
            WithdrawalRequest.created_at >= start,
            WithdrawalRequest.created_at < end,
            WithdrawalRequest.status.in_(["pending", "approved"]),
        )
        .scalar()
        or 0
    )
    pending_withdraw_count = (
        db.query(func.count(WithdrawalRequest.id))
        .filter(
            WithdrawalRequest.created_at >= start,
            WithdrawalRequest.created_at < end,
            WithdrawalRequest.status.in_(["pending", "approved"]),
        )
        .scalar()
    )

    return {
        "day": start.strftime("%Y-%m-%d"),
        "orders": {
            "count": int(order_count or 0),
            "order_amount_total": round(float(order_amount_total), 2),
            "commission_total": round(float(commission_total), 2),
            "settled_rebate_total": round(float(settled_rebate_total), 2),
        },
        "payout": {
            "paid_total": round(float(payout_total), 2),
            "pending_withdraw_count": int(pending_withdraw_count or 0),
            "pending_withdraw_total": round(float(pending_withdraw_total), 2),
        },
        "profit_estimate": round(float(commission_total) - float(payout_total), 2),
    }
