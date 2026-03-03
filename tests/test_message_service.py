from app.services.message_service import MessageService


def test_parse_payout_content_with_channel_prefix():
    svc = MessageService()
    parsed = svc._parse_payout_content("支付宝: demo@example.com")
    assert parsed is not None
    channel, account, account_name = parsed
    assert channel == "alipay"
    assert account == "demo@example.com"
    assert account_name is None


def test_parse_payout_content_default_wechat():
    svc = MessageService()
    parsed = svc._parse_payout_content("wxid_abc123")
    assert parsed is not None
    channel, account, account_name = parsed
    assert channel == "wechat"
    assert account == "wxid_abc123"
    assert account_name is None


def test_mask_account():
    assert MessageService._mask_account("123456789") == "123***789"
