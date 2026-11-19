"""Only manually verified, article-specific forum links may be published."""

import re
from urllib.parse import urlparse


def is_verified_review_url(url: str, forum: str) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.query or parsed.fragment:
        return False
    if forum == "dcard":
        return parsed.netloc in ("dcard.tw", "www.dcard.tw") and bool(
            re.fullmatch(r"/f/[^/]+/p/[0-9]+", parsed.path)
        )
    if forum == "ptt":
        return parsed.netloc in ("ptt.cc", "www.ptt.cc") and bool(
            re.fullmatch(r"/bbs/[^/]+/M\.[0-9]+\.A\.[A-Za-z0-9]+\.html", parsed.path)
        )
    return False


def verified_review_links(value):
    if not isinstance(value, dict):
        return {}
    result = {}
    for forum in ("dcard", "ptt"):
        url = value.get(f"{forum}_url")
        if value.get(f"{forum}_verified") is True and is_verified_review_url(url, forum):
            result[f"{forum}_url"] = url
            result[f"{forum}_verified"] = True
    return result
