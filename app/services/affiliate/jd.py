from app.services.affiliate.base import AffiliateQuote, BaseAffiliateAdapter, stable_number


class JDAffiliateAdapter(BaseAffiliateAdapter):
    platform_name = "jd"

    def get_quote(self, product_id: str, source_url: str) -> AffiliateQuote:
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
