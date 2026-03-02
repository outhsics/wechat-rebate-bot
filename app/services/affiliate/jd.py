import hashlib
import json
from datetime import datetime

import httpx

from app.config import get_settings
from app.services.affiliate.base import AffiliateQuote, BaseAffiliateAdapter, stable_number


class JDAffiliateAdapter(BaseAffiliateAdapter):
    platform_name = "jd"

    def get_quote(self, product_id: str, source_url: str) -> AffiliateQuote:
        quote = self._query_real_quote(product_id, source_url)
        if quote:
            return quote

        # Fallback to deterministic mock to keep runtime stable before API credentials are ready.
        final_price = stable_number(f"jd:{product_id}:price", 39, 499)
        coupon = stable_number(f"jd:{product_id}:coupon", 3, 50)
        commission = stable_number(f"jd:{product_id}:commission", 1.5, 25)
        return AffiliateQuote(
            platform="jd",
            product_id=product_id,
            product_title=f"京东商品 {product_id}",
            final_price=max(1, round(final_price - coupon, 2)),
            coupon_amount=coupon,
            commission_amount=commission,
            buy_url=source_url,
        )

    def _query_real_quote(self, product_id: str, source_url: str) -> AffiliateQuote | None:
        settings = get_settings()
        if not settings.jd_affiliate_app_key or not settings.jd_affiliate_app_secret:
            return None

        goods_req = {
            "goodsReqDTO": {
                "eliteId": settings.jd_affiliate_elite_id,
                "skuIds": [product_id],
            }
        }

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sys_params: dict[str, str] = {
            "method": settings.jd_affiliate_method,
            "app_key": settings.jd_affiliate_app_key,
            "timestamp": timestamp,
            "format": "json",
            "v": "1.0",
            "sign_method": "md5",
            "param_json": json.dumps(goods_req, ensure_ascii=False, separators=(",", ":")),
        }
        if settings.jd_affiliate_access_token:
            sys_params["access_token"] = settings.jd_affiliate_access_token

        sys_params["sign"] = self._sign(sys_params, settings.jd_affiliate_app_secret)

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(settings.jd_affiliate_api_url, data=sys_params)
                resp.raise_for_status()
                payload = resp.json()
        except Exception:
            return None

        item = self._extract_item(payload)
        if not item:
            return None

        title = str(item.get("goodsName") or item.get("skuName") or f"京东商品 {product_id}")
        price = self._to_float(item.get("priceInfo", {}).get("price"))
        if price <= 0:
            price = self._to_float(item.get("unitPrice"))
        coupon_list = item.get("couponInfo", {}).get("couponList")
        coupon_item = coupon_list[0] if isinstance(coupon_list, list) and coupon_list else {}
        lowest_coupon = self._to_float(coupon_item.get("discount"))
        commission = self._to_float(item.get("commissionInfo", {}).get("commission"))
        if commission <= 0:
            rate = self._to_float(item.get("commissionInfo", {}).get("commissionShare"))
            if rate > 0 and price > 0:
                commission = round(price * rate / 100, 2)

        final_price = max(1, round(price - lowest_coupon, 2)) if price > 0 else 0.0
        if final_price <= 0 or commission <= 0:
            return None

        return AffiliateQuote(
            platform="jd",
            product_id=product_id,
            product_title=title,
            final_price=final_price,
            coupon_amount=lowest_coupon,
            commission_amount=commission,
            buy_url=source_url,
        )

    @staticmethod
    def _sign(params: dict[str, str], app_secret: str) -> str:
        sorted_pairs = sorted((k, v) for k, v in params.items() if k and v is not None and k != "sign")
        sign_raw = app_secret + "".join(f"{k}{v}" for k, v in sorted_pairs) + app_secret
        return hashlib.md5(sign_raw.encode("utf-8")).hexdigest().upper()

    def _extract_item(self, payload: dict) -> dict | None:
        # The union API usually nests result JSON in "xxx_responce" -> "queryResult" as a string.
        top_level = next((v for k, v in payload.items() if k.endswith("responce")), None)
        if not isinstance(top_level, dict):
            return None

        query_result = top_level.get("queryResult")
        if isinstance(query_result, str):
            try:
                query_result = json.loads(query_result)
            except json.JSONDecodeError:
                return None
        if not isinstance(query_result, dict):
            return None

        data = query_result.get("data")
        if not isinstance(data, list) or not data:
            return None

        first = data[0]
        return first if isinstance(first, dict) else None

    @staticmethod
    def _to_float(value) -> float:
        try:
            return round(float(value), 2)
        except Exception:
            return 0.0
