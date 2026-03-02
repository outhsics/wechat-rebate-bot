from app.services.parser import parse_affiliate_input


def test_parse_jd():
    text = "看下这个 https://item.jd.com/100012043978.html"
    parsed = parse_affiliate_input(text)
    assert parsed is not None
    assert parsed.platform == "jd"
    assert parsed.product_id == "100012043978"


def test_parse_pdd():
    text = "https://mobile.yangkeduo.com/goods.html?goods_id=123456789"
    parsed = parse_affiliate_input(text)
    assert parsed is not None
    assert parsed.platform == "pdd"
    assert parsed.product_id == "123456789"


def test_parse_taobao():
    text = "https://item.taobao.com/item.htm?id=987654321"
    parsed = parse_affiliate_input(text)
    assert parsed is not None
    assert parsed.platform == "taobao"
    assert parsed.product_id == "987654321"


def test_parse_unknown():
    parsed = parse_affiliate_input("你好，今天吃什么")
    assert parsed is None
