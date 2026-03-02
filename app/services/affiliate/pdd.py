from app.services.affiliate.base import AffiliateQuote, BaseAffiliateAdapter, stable_number


class PDDAffiliateAdapter(BaseAffiliateAdapter):
    platform_name = "pdd"

    def get_quote(self, product_id: str, source_url: str) -> AffiliateQuote:
        final_price = stable_number(f"pdd:{product_id}:price", 9.9, 299)
        coupon = stable_number(f"pdd:{product_id}:coupon", 1, 40)
        commission = stable_number(f"pdd:{product_id}:commission", 1, 20)
        return AffiliateQuote(
            platform="pdd",
            product_id=product_id,
            product_title=f"拼多多商品 {product_id}",
            final_price=max(1, round(final_price - coupon, 2)),
            coupon_amount=coupon,
            commission_amount=commission,
            buy_url=source_url,
        )
