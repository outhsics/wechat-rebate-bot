from dataclasses import dataclass
from hashlib import sha1


@dataclass
class AffiliateQuote:
    platform: str
    product_id: str
    product_title: str
    final_price: float
    coupon_amount: float
    commission_amount: float
    buy_url: str


class BaseAffiliateAdapter:
    platform_name: str = "unknown"

    def get_quote(self, product_id: str, source_url: str) -> AffiliateQuote:
        raise NotImplementedError


def stable_number(seed: str, minimum: float, maximum: float, digits: int = 2) -> float:
    raw = int(sha1(seed.encode("utf-8")).hexdigest()[:8], 16)
    ratio = raw / 0xFFFFFFFF
    value = minimum + (maximum - minimum) * ratio
    return round(value, digits)
