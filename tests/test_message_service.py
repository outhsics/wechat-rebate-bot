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


def test_rate_limit_hits_after_threshold():
    svc = MessageService()
    svc.settings.message_rate_limit_per_min = 1
    limited, retry_after = svc._is_rate_limited("openid_demo")
    assert not limited
    assert retry_after == 0

    limited, retry_after = svc._is_rate_limited("openid_demo")
    assert limited
    assert retry_after > 0


def test_extract_withdraw_amount():
    svc = MessageService()
    assert svc._extract_withdraw_amount("申请提现 12.8") == 12.8
    assert svc._extract_withdraw_amount("提现") is None
