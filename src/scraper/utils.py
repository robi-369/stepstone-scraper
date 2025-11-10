import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

logger = logging.getLogger("scraper")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def save_json(obj: Any, path: str) -> None:
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def clean_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return " ".join(s.replace("\xa0", " ").split())

def parse_date(val: Optional[str]) -> str:
    if not val:
        return ""
    try:
        dt = dateparser.parse(val, fuzzy=True)
        if not dt:
            return ""
        return dt.date().isoformat()
    except Exception:
        return ""

def make_absolute_url(base: str, href: str) -> str:
    if not href:
        return base
    return urljoin(base if base.endswith("/") else base + "/", href)

def pick_user_agent(request_conf: Optional[Dict[str, Any]]) -> str:
    if request_conf and request_conf.get("user_agents"):
        return random.choice(request_conf["user_agents"])
    return request_conf.get("user_agent") if request_conf else DEFAULT_UA

def fetch_html(
    url: str,
    request_conf: Optional[Dict[str, Any]] = None,
    retry: int = 2,
    backoff: float = 1.0,
) -> Tuple[str, Optional[BeautifulSoup], int]:
    """
    Fetches a URL returning (html, BeautifulSoup, status_code).
    Applies simple retries and optional proxy/cookie headers from request_conf.
    """
    headers = {"User-Agent": pick_user_agent(request_conf)}
    cookies = request_conf.get("cookies") if request_conf else None
    proxies = request_conf.get("proxies") if request_conf else None
    timeout = float(request_conf.get("timeout", 15)) if request_conf else 15.0

    last_exc = None
    for attempt in range(retry + 1):
        try:
            resp = requests.get(url, headers=headers, cookies=cookies, proxies=proxies, timeout=timeout)
            status = resp.status_code
            if status >= 500 and attempt < retry:
                time.sleep(backoff * (attempt + 1))
                continue
            html = resp.text if resp.ok else ""
            soup = BeautifulSoup(html, "lxml") if html else None
            return html, soup, status
        except Exception as e:
            last_exc = e
            if attempt < retry:
                time.sleep(backoff * (attempt + 1))
            else:
                logger.error("fetch_html error %s on %s", e, url)

    return "", None, 0 if last_exc is None else 599

def unique_by_key(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for x in items:
        k = x.get(key)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out

def chunked(seq: Iterable[Any], size: int) -> Iterable[List[Any]]:
    buf: List[Any] = []
    for item in seq:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf