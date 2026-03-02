import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)


@dataclass
class ParsedProduct:
    platform: str
    product_id: str
    source_url: str


def _extract_first_url(text: str) -> str | None:
    match = URL_PATTERN.search(text)
    if not match:
        return None
    return match.group(0).rstrip("，。,.!！;；")


def _parse_jd(url: str) -> str | None:
    m = re.search(r"item\.jd\.com/(\d+)\.html", url)
    if m:
        return m.group(1)

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "sku" in qs and qs["sku"]:
        return qs["sku"][0]
    return None


def _parse_pdd(url: str) -> str | None:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in ("goods_id", "goodsId"):
        if key in qs and qs[key]:
            return qs[key][0]
    m = re.search(r"goods_id=(\d+)", url)
    return m.group(1) if m else None


def _parse_taobao(url: str) -> str | None:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "id" in qs and qs["id"]:
        return qs["id"][0]

    m = re.search(r"[?&]id=(\d+)", url)
    return m.group(1) if m else None


def parse_affiliate_input(text: str) -> ParsedProduct | None:
    url = _extract_first_url(text)
    if not url:
        return None

    lower = url.lower()
    if "jd.com" in lower:
        product_id = _parse_jd(url)
        if product_id:
            return ParsedProduct(platform="jd", product_id=product_id, source_url=url)

    if "yangkeduo.com" in lower or "pinduoduo.com" in lower or "pdd" in lower:
        product_id = _parse_pdd(url)
        if product_id:
            return ParsedProduct(platform="pdd", product_id=product_id, source_url=url)

    if "taobao.com" in lower or "tmall.com" in lower:
        product_id = _parse_taobao(url)
        if product_id:
            return ParsedProduct(platform="taobao", product_id=product_id, source_url=url)

    return None
