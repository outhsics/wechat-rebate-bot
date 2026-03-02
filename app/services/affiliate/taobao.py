from app.services.affiliate.base import AffiliateQuote, BaseAffiliateAdapter, stable_number


class TaobaoAffiliateAdapter(BaseAffiliateAdapter):
    platform_name = "taobao"

    def get_quote(self, product_id: str, source_url: str) -> AffiliateQuote:
        final_price = stable_number(f"taobao:{product_id}:price", 19.9, 899)
        coupon = stable_number(f"taobao:{product_id}:coupon", 3, 120)
        commission = stable_number(f"taobao:{product_id}:commission", 1.5, 80)
        return AffiliateQuote(
            platform="taobao",
            product_id=product_id,
            product_title=f"淘宝/天猫商品 {product_id}",
            final_price=max(1, round(final_price - coupon, 2)),
            coupon_amount=coupon,
            commission_amount=commission,
            buy_url=source_url,
        )
