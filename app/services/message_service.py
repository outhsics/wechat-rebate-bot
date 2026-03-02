from sqlalchemy.orm import Session

from app.models import LinkLog, User
from app.services.ai_service import AIService
from app.services.parser import parse_affiliate_input
from app.services.rebate_service import RebateService


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
