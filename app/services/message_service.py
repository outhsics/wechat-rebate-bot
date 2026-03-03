import re
import time
from collections import defaultdict, deque
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    ConversationState,
    LinkLog,
    Order,
    PayoutAccount,
    PayoutRecord,
    RiskBlocklist,
    User,
    WithdrawalRequest,
)
from app.services.ai_service import AIService
from app.services.parser import parse_affiliate_input
from app.services.rebate_service import RebateService

BIND_PAYOUT_COMMANDS = {"绑定收款", "绑定收款账号", "绑定提现", "绑定提现账号"}
SHOW_PAYOUT_COMMANDS = {"查看收款", "我的收款", "收款账号"}
WITHDRAW_COMMANDS = {"提现", "申请提现"}
SHOW_BALANCE_COMMANDS = {"提现余额", "可提现", "我的返利", "余额"}
CANCEL_COMMANDS = {"取消", "退出", "算了"}


class MessageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.ai_service = AIService()
        self.rebate_service = RebateService()
        self._recent_messages: dict[str, deque[float]] = defaultdict(deque)

    def _get_or_create_user(self, db: Session, openid: str) -> User:
        user = db.query(User).filter(User.openid == openid).first()
        if user:
            return user
        user = User(openid=openid)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def _upsert_state(self, db: Session, openid: str, state: str) -> None:
        row = db.query(ConversationState).filter(ConversationState.openid == openid).first()
        if row:
            row.state = state
        else:
            row = ConversationState(openid=openid, state=state)
            db.add(row)
        db.commit()

    def _clear_state(self, db: Session, openid: str) -> None:
        row = db.query(ConversationState).filter(ConversationState.openid == openid).first()
        if row:
            db.delete(row)
            db.commit()

    def _get_state(self, db: Session, openid: str) -> str | None:
        row = db.query(ConversationState).filter(ConversationState.openid == openid).first()
        return row.state if row else None

    def _parse_payout_content(self, content: str) -> tuple[str, str, str | None] | None:
        text = content.strip()
        if not text:
            return None

        # Example: 支付宝:abc@xx.com / 微信:wxid_xxx / 银行卡:6222...
        if ":" in text or "：" in text:
            pair = re.split(r"[:：]", text, maxsplit=1)
            left = pair[0].strip()
            right = pair[1].strip() if len(pair) > 1 else ""
            if not right:
                return None
            return self._to_channel(left), right, None

        lower = text.lower()
        if lower.startswith("支付宝"):
            return "alipay", text.replace("支付宝", "", 1).strip(), None
        if lower.startswith("微信"):
            return "wechat", text.replace("微信", "", 1).strip(), None
        if lower.startswith("银行卡"):
            return "bank", text.replace("银行卡", "", 1).strip(), None

        # Fallback: treat as WeChat account.
        return "wechat", text, None

    @staticmethod
    def _to_channel(raw: str) -> str:
        key = raw.strip().lower()
        if "支付" in key:
            return "alipay"
        if "银行" in key:
            return "bank"
        return "wechat"

    @staticmethod
    def _mask_account(account: str) -> str:
        if len(account) <= 6:
            return account
        return f"{account[:3]}***{account[-3:]}"

    def _save_payout_account(
        self,
        db: Session,
        user: User,
        openid: str,
        channel: str,
        account: str,
        account_name: str | None = None,
    ) -> PayoutAccount:
        row = (
            db.query(PayoutAccount)
            .filter(PayoutAccount.openid == openid, PayoutAccount.is_active == 1)
            .first()
        )
        if row:
            row.channel = channel
            row.account = account
            row.account_name = account_name
        else:
            row = PayoutAccount(
                user_id=user.id,
                openid=openid,
                channel=channel,
                account=account,
                account_name=account_name,
                is_active=1,
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def _show_payout_account(self, db: Session, openid: str) -> str:
        row = (
            db.query(PayoutAccount)
            .filter(PayoutAccount.openid == openid, PayoutAccount.is_active == 1)
            .first()
        )
        if not row:
            return "你还没绑定收款账号。发送“绑定收款”开始绑定。"
        return (
            "当前收款账号：\n"
            f"渠道：{row.channel}\n"
            f"账号：{self._mask_account(row.account)}\n"
            "如需修改，请发送“绑定收款”。"
        )

    def _is_rate_limited(self, openid: str) -> tuple[bool, int]:
        limit = max(1, int(self.settings.message_rate_limit_per_min))
        now = time.time()
        time_window = 60

        queue = self._recent_messages[openid]
        while queue and now - queue[0] >= time_window:
            queue.popleft()

        if len(queue) >= limit:
            retry_after = max(1, int(time_window - (now - queue[0])))
            return True, retry_after

        queue.append(now)
        return False, 0

    @staticmethod
    def _is_blocked(db: Session, openid: str) -> bool:
        row = (
            db.query(RiskBlocklist)
            .filter(RiskBlocklist.openid == openid, RiskBlocklist.is_active == 1)
            .first()
        )
        return row is not None

    @staticmethod
    def _extract_withdraw_amount(content: str) -> float | None:
        match = re.search(r"(\d+(?:\.\d{1,2})?)", content)
        if not match:
            return None
        try:
            value = float(match.group(1))
        except ValueError:
            return None
        if value <= 0:
            return None
        return round(value, 2)

    def _get_available_balance(self, db: Session, openid: str) -> float:
        settled_total = (
            db.query(func.sum(Order.rebate_amount))
            .filter(Order.raw_openid == openid, Order.status.in_(["settled", "paid_out"]))
            .scalar()
            or 0
        )
        paid_total = (
            db.query(func.sum(PayoutRecord.amount))
            .filter(PayoutRecord.openid == openid, PayoutRecord.status.in_(["confirmed", "paid"]))
            .scalar()
            or 0
        )
        withdrawing_total = (
            db.query(func.sum(WithdrawalRequest.amount))
            .filter(
                WithdrawalRequest.openid == openid,
                WithdrawalRequest.status.in_(["pending", "approved"]),
            )
            .scalar()
            or 0
        )
        return round(max(0.0, float(settled_total) - float(paid_total) - float(withdrawing_total)), 2)

    def _show_withdraw_balance(self, db: Session, openid: str) -> str:
        amount = self._get_available_balance(db, openid)
        return (
            f"当前可提现余额：¥{amount}\n"
            "发送“申请提现 10”即可提交提现工单。"
        )

    def _create_withdraw_request(
        self,
        db: Session,
        user: User,
        openid: str,
        amount: float,
    ) -> WithdrawalRequest:
        row = WithdrawalRequest(
            id=f"wd_{uuid4().hex[:18]}",
            user_id=user.id,
            openid=openid,
            amount=amount,
            status="pending",
            note="user_submit",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def handle_message(self, db: Session, payload: dict[str, str]) -> str | None:
        msg_type = payload.get("MsgType", "")
        from_user = payload.get("FromUserName", "")

        if not from_user:
            return None

        user = self._get_or_create_user(db, from_user)

        if msg_type == "event":
            event = payload.get("Event", "").lower()
            if event == "subscribe":
                return (
                    "欢迎关注返利机器人。\n"
                    "直接发送京东/拼多多/淘宝商品链接，我会返回券后价和预计返利。"
                )
            return "已收到你的操作。发送商品链接即可查询返利。"

        if msg_type != "text":
            return "暂时只支持文本消息。请发送商品链接进行返利查询。"

        content = payload.get("Content", "").strip()
        limited, retry_after = self._is_rate_limited(from_user)
        if limited:
            return f"消息太频繁了，请 {retry_after} 秒后再试。"
        if self._is_blocked(db, from_user):
            return "账号当前处于风控状态，请联系客服处理。"

        if content in BIND_PAYOUT_COMMANDS:
            self._upsert_state(db, from_user, "bind_payout_account")
            return (
                "请发送你的收款账号，格式示例：\n"
                "支付宝: your_account@example.com\n"
                "微信: wxid_xxx\n"
                "银行卡: 6222xxxx\n"
                "发送“取消”可退出绑定。"
            )

        if content in SHOW_PAYOUT_COMMANDS:
            return self._show_payout_account(db, from_user)

        if content in SHOW_BALANCE_COMMANDS:
            return self._show_withdraw_balance(db, from_user)

        if any(content.startswith(x) for x in WITHDRAW_COMMANDS):
            payout = (
                db.query(PayoutAccount)
                .filter(PayoutAccount.openid == from_user, PayoutAccount.is_active == 1)
                .first()
            )
            if not payout:
                return "你还没绑定收款账号。请先发送“绑定收款”。"

            amount = self._extract_withdraw_amount(content)
            if amount is None:
                return "请按格式发送：申请提现 10"

            min_amount = float(self.settings.min_withdraw_amount)
            if amount < min_amount:
                return f"单次提现金额不能低于 ¥{min_amount}。"

            available = self._get_available_balance(db, from_user)
            if amount > available:
                return f"余额不足，可提现 ¥{available}。"

            request = self._create_withdraw_request(db, user, from_user, amount)
            return (
                f"提现申请已提交：{request.id}\n"
                f"金额：¥{amount}\n"
                "状态：待审核。"
            )

        state = self._get_state(db, from_user)
        if state == "bind_payout_account":
            if content in CANCEL_COMMANDS:
                self._clear_state(db, from_user)
                return "已取消绑定。"
            parsed_account = self._parse_payout_content(content)
            if not parsed_account:
                return "格式不对，请按“支付宝:账号”或“微信:账号”发送。"

            channel, account, account_name = parsed_account
            row = self._save_payout_account(
                db=db,
                user=user,
                openid=from_user,
                channel=channel,
                account=account,
                account_name=account_name,
            )
            self._clear_state(db, from_user)
            return (
                "收款账号已绑定成功：\n"
                f"渠道：{row.channel}\n"
                f"账号：{self._mask_account(row.account)}\n"
                "后续返利确认后会按该账号打款。"
            )

        parsed = parse_affiliate_input(content)
        if parsed:
            result = self.rebate_service.quote(parsed)
            log = LinkLog(
                user_id=user.id,
                raw_openid=from_user,
                raw_text=content,
                platform=result.platform,
                product_id=result.product_id,
                quote_price=result.final_price,
                quote_commission=result.commission_amount,
                quote_rebate=result.rebate_amount,
            )
            db.add(log)
            db.commit()

            return (
                f"【{result.title}】\n"
                f"平台：{result.platform.upper()}\n"
                f"券后价：¥{result.final_price}\n"
                f"预计佣金：¥{result.commission_amount}\n"
                f"预计返利：¥{result.rebate_amount}\n"
                f"返利码：{result.rebate_code}\n"
                f"下单链接：{result.buy_url}\n"
                "提示：实际返利以联盟结算为准。"
            )

        return self.ai_service.reply(content)
