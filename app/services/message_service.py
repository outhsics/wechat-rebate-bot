import re

from sqlalchemy.orm import Session

from app.models import ConversationState, LinkLog, PayoutAccount, User
from app.services.ai_service import AIService
from app.services.parser import parse_affiliate_input
from app.services.rebate_service import RebateService

BIND_PAYOUT_COMMANDS = {"绑定收款", "绑定收款账号", "绑定提现", "绑定提现账号"}
SHOW_PAYOUT_COMMANDS = {"查看收款", "我的收款", "收款账号"}
CANCEL_COMMANDS = {"取消", "退出", "算了"}


class MessageService:
    def __init__(self) -> None:
        self.ai_service = AIService()
        self.rebate_service = RebateService()

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
