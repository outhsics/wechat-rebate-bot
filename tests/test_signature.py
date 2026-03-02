import hashlib

from app.wechat.signature import verify_wechat_signature


def test_verify_wechat_signature():
    token = "abc123"
    timestamp = "1700000000"
    nonce = "999"
    sign = hashlib.sha1("".join(sorted([token, timestamp, nonce])).encode("utf-8")).hexdigest()
    assert verify_wechat_signature(token, sign, timestamp, nonce)
    assert not verify_wechat_signature(token, "bad", timestamp, nonce)
