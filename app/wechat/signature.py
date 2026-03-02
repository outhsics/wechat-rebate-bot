import hashlib


def verify_wechat_signature(token: str, signature: str, timestamp: str, nonce: str) -> bool:
    parts = sorted([token, timestamp, nonce])
    joined = "".join(parts)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()
    return digest == signature
