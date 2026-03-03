from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    openid: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    nickname: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    link_logs: Mapped[list["LinkLog"]] = relationship("LinkLog", back_populates="user")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")
    payout_accounts: Mapped[list["PayoutAccount"]] = relationship("PayoutAccount", back_populates="user")


class LinkLog(Base):
    __tablename__ = "link_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    raw_openid: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    quote_price: Mapped[float] = mapped_column(Float, nullable=False)
    quote_commission: Mapped[float] = mapped_column(Float, nullable=False)
    quote_rebate: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[Optional[User]] = relationship("User", back_populates="link_logs")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    raw_openid: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_amount: Mapped[float] = mapped_column(Float, nullable=False)
    commission_amount: Mapped[float] = mapped_column(Float, nullable=False)
    rebate_amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[Optional[User]] = relationship("User", back_populates="orders")


class PayoutAccount(Base):
    __tablename__ = "payout_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    openid: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="wechat")
    account: Mapped[str] = mapped_column(String(128), nullable=False)
    account_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[Optional[User]] = relationship("User", back_populates="payout_accounts")


class ConversationState(Base):
    __tablename__ = "conversation_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    openid: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PayoutRecord(Base):
    __tablename__ = "payout_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    openid: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    account: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="confirmed")
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
