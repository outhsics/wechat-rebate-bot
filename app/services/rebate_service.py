from dataclasses import dataclass
from hashlib import sha1

from app.config import get_settings
from app.services.affiliate.base import AffiliateQuote
from app.services.affiliate.jd import JDAffiliateAdapter
from app.services.affiliate.pdd import PDDAffiliateAdapter
from app.services.affiliate.taobao import TaobaoAffiliateAdapter
from app.services.parser import ParsedProduct


@dataclass
class RebateResult:
    platform: str
    product_id: str
    title: str
    final_price: float
    coupon_amount: float
    commission_amount: float
    rebate_amount: float
    rebate_code: str
    buy_url: str


class RebateService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.adapters = {
            "jd": JDAffiliateAdapter(),
            "pdd": PDDAffiliateAdapter(),
            "taobao": TaobaoAffiliateAdapter(),
        }

    def quote(self, product: ParsedProduct) -> RebateResult:
        adapter = self.adapters.get(product.platform)
        if not adapter:
            raise ValueError(f"Unsupported platform: {product.platform}")

        quote: AffiliateQuote = adapter.get_quote(product.product_id, product.source_url)
        rebate_amount = round(quote.commission_amount * self.settings.rebate_rate, 2)
        rebate_code = sha1(f"{quote.platform}:{quote.product_id}".encode("utf-8")).hexdigest()[:10]

        return RebateResult(
            platform=quote.platform,
            product_id=quote.product_id,
            title=quote.product_title,
            final_price=quote.final_price,
            coupon_amount=quote.coupon_amount,
            commission_amount=quote.commission_amount,
            rebate_amount=rebate_amount,
            rebate_code=rebate_code,
            buy_url=quote.buy_url,
        )
