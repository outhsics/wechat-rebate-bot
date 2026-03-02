from app.services.affiliate.jd import JDAffiliateAdapter


def test_jd_sign_stable():
    params = {
        "method": "jd.union.open.goods.jingfen.query",
        "app_key": "demo_key",
        "timestamp": "2026-03-02 20:00:00",
        "format": "json",
        "v": "1.0",
        "sign_method": "md5",
        "param_json": '{"goodsReqDTO":{"eliteId":1,"skuIds":["10001"]}}',
    }
    sign = JDAffiliateAdapter._sign(params, "demo_secret")
    assert isinstance(sign, str)
    assert len(sign) == 32
    assert sign.upper() == sign


def test_extract_item_from_response():
    adapter = JDAffiliateAdapter()
    payload = {
        "jd_union_open_goods_jingfen_query_responce": {
            "queryResult": (
                '{"code":200,"data":[{"goodsName":"test","priceInfo":{"price":99.9},'
                '"commissionInfo":{"commission":9.9},"couponInfo":{"couponList":[{"discount":5}]}}]}'
            )
        }
    }
    item = adapter._extract_item(payload)
    assert item is not None
    assert item["goodsName"] == "test"
