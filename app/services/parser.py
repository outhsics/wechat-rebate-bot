import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx


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


def _parse_from_url(url: str) -> ParsedProduct | None:
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


def _expand_short_url(url: str) -> str | None:
    try:
        with httpx.Client(
            timeout=4.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            resp = client.get(url)
            final_url = str(resp.url)
            if final_url and final_url != url:
                return final_url
    except Exception:
        return None
    return None


def parse_affiliate_input(text: str) -> ParsedProduct | None:
    url = _extract_first_url(text)
    if not url:
        return None

    parsed = _parse_from_url(url)
    if parsed:
        return parsed

    # For short links like u.jd.com, try resolving redirection first.
    expanded_url = _expand_short_url(url)
    if expanded_url:
        parsed = _parse_from_url(expanded_url)
        if parsed:
            return parsed

    return None
