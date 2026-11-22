"""HTTP layer for lcwaikiki_mcp — Chrome TLS impersonation required.

www.lcw.com returns HTTP 403 "Access Denied" (Akamai) to plain
curl/httpx with a browser UA (verified live 2026-11-22: 403 on the
search page AND the product-list AJAX endpoint with plain curl), but
answers HTTP 200 to curl-cffi chrome131 impersonation. The site is a
React SPA whose search/category listings are server-rendered pages
embedding a catalogModel JSON blob — no login, no API key, no
cookies needed. (The product-list AJAX endpoint exists but reports
pre-campaign prices that disagree with the product pages, and
returns only a generic fallback for categories — so listings use
HTML.) Requests are kept gentle (one at a time, ~0.8s apart) and
read-only.
"""
from __future__ import annotations

import time
from urllib.parse import quote_plus, urlparse

from curl_cffi import requests as _r

BASE = "https://www.lcw.com"
TIMEOUT = 30.0
MIN_INTERVAL = 0.8  # seconds between requests — be polite

_HEADERS = {
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": "https://www.lcw.com/",
}
_last_fetch = 0.0


class LcwaikikiError(RuntimeError):
    pass


_PROFILES = ("chrome131", "chrome120", "safari17_0")
_MAX_ATTEMPTS = 2  # one retry with the next profile
_RETRY_BACKOFF = 1.0  # seconds between attempts
_profile_idx = 0  # sticky: profile that last succeeded


def _request(url: str, headers: dict, timeout: float = TIMEOUT):
    """GET with fingerprint rotation.

    Starts at the sticky profile (chrome131 on a fresh process), retries
    once with the next profile on HTTP 403/429 or a transport error, then
    returns the last response (so the caller raises the specific 403/429
    error) or raises a network error if every attempt failed at the
    transport.
    """
    global _profile_idx
    last_exc: Exception | None = None
    for k in range(_MAX_ATTEMPTS):
        profile = _PROFILES[(_profile_idx + k) % len(_PROFILES)]
        try:
            resp = _r.get(url, impersonate=profile, headers=headers, timeout=timeout)
        except Exception as e:
            last_exc = e
            if k + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF)
                continue
            raise LcwaikikiError(f"network error fetching {url}: {e}") from e
        if resp.status_code in (403, 429):
            if k + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF)
                continue
            return resp
        _profile_idx = (_profile_idx + k) % len(_PROFILES)
        return resp
    raise LcwaikikiError(f"network error fetching {url}: {last_exc}") from last_exc


def _get_resp(url: str, headers: dict | None = None):
    """Rate-limited GET returning the raw response (no status checks)."""
    global _last_fetch
    wait = MIN_INTERVAL - (time.monotonic() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = _request(url, headers or _HEADERS)
    except LcwaikikiError:
        raise
    except Exception as e:
        raise LcwaikikiError(f"network error fetching {url}: {e}") from e
    finally:
        _last_fetch = time.monotonic()
    return resp


def _get(url: str, headers: dict | None = None) -> str:
    resp = _get_resp(url, headers)
    if resp.status_code == 403:
        raise LcwaikikiError(
            "lcw.com refused the request (HTTP 403, bot wall) — try again later"
        )
    if resp.status_code == 429:
        raise LcwaikikiError(
            "lcw.com rate-limited the request (HTTP 429) — try again later"
        )
    if resp.status_code == 404:
        raise LcwaikikiError(f"page not found (HTTP 404): {url}")
    if resp.status_code != 200:
        raise LcwaikikiError(f"unexpected HTTP {resp.status_code} fetching {url}")
    return resp.text


def fetch_search_html(query: str, sort_param: str | None = None, page: int = 1) -> str | None:
    """Search results as a server-rendered HTML page (/arama?q=…).

    Returns None when the site has no matches (it answers such a
    search with HTTP 404 "sonuç bulunamadı").

    NOTE: the product-list AJAX endpoint reports a HIGHER PriceValue
    than the product pages show (verified live 2026-11-22: the same
    dress is 989.99 via AJAX but 649.99 on its detail page and on the
    HTML search page — the AJAX figure looks like the pre-campaign
    price). The HTML page embeds the identical catalogModel with the
    prices the detail pages show, so search uses HTML: paging via
    ?sayfa=N, sorting via ?Sort=PriceASC (and the other Sort values).
    """
    url = f"{BASE}/arama?q={quote_plus(query)}"
    params = []
    if page > 1:
        params.append(f"sayfa={page}")
    if sort_param:
        params.append(f"Sort={sort_param}")
    if params:
        url += "&" + "&".join(params)
    resp = _get_resp(url)
    if resp.status_code == 404 and "sonuç bulunamadı" in resp.text:
        return None  # the site 404s a search with no matches
    if resp.status_code == 403:
        raise LcwaikikiError(
            "lcw.com refused the request (HTTP 403, bot wall) — try again later"
        )
    if resp.status_code == 429:
        raise LcwaikikiError(
            "lcw.com rate-limited the request (HTTP 429) — try again later"
        )
    if resp.status_code != 200:
        raise LcwaikikiError(f"unexpected HTTP {resp.status_code} fetching {url}")
    return resp.text


def fetch_category_html(path: str, sort_param: str | None = None, page: int = 1) -> str:
    """One category's product list as a server-rendered HTML page.

    NOTE: the product-list AJAX endpoint does NOT serve categories from
    a stateless request — called with CategoryTreeId it returns the
    site's 52-item generic fallback (ProductFound false, verified live
    2026-11-22 for ids 10 and 45), and calling it inside a session
    hangs (Akamai holds the request). The category HTML page itself
    embeds the full catalogModel (24,469 items for Kadın Giyim), so
    categories are fetched as HTML: /<slug>-t-<id>[?sayfa=N][&Sort=…].
    path: "/kadin-giyim-t-10" (from lcwaikiki_list_categories).
    sort_param: same values as the search endpoint.
    """
    url = f"{BASE}{path}"
    params = []
    if page > 1:
        params.append(f"sayfa={page}")
    if sort_param:
        params.append(f"Sort={sort_param}")
    if params:
        url += "?" + "&".join(params)
    return _get(url)


def fetch_product_html(product: str) -> str:
    """Product detail page HTML.

    product: a full lcw.com product URL or a site path, e.g.
    "/cicekli-kiz-cocuk-kadife-elbise-haki-o-5657836" (the "-o-<id>"
    suffix is how LCW identifies a product option — find one with
    lcwaikiki_search_products first).
    """
    path = product.strip()
    if path.startswith("http"):
        parsed = urlparse(path)
        if "lcw.com" not in parsed.netloc and "lcwaikiki.com" not in parsed.netloc:
            raise LcwaikikiError("product must be an lcw.com / lcwaikiki.com URL or path")
        path = parsed.path
    if not path.startswith("/"):
        path = "/" + path
    if "-o-" not in path:
        raise LcwaikikiError(
            "product must be a product URL/path containing '-o-<id>' "
            "(find one with lcwaikiki_search_products first)"
        )
    return _get(f"{BASE}{path}")


def fetch_all_categories_html() -> str:
    """The "all categories" directory page (mega-menu navigation)."""
    return _get(f"{BASE}/tum-kategoriler-u-6000009")


def fetch_home_html() -> str:
    return _get(f"{BASE}/")


def health_check() -> dict:
    """Two polite probes of the source site (home page + one search).

    Returns {"status": "ok"|"blocked"|"error", "http_status": int|None,
    "url": ..., "detail": ...}. Used by the `lcwaikiki_health` tool.
    """
    url = f"{BASE}/"
    try:
        fetch_home_html()
        fetch_search_html("elbise", page=1)
    except LcwaikikiError as e:
        msg = str(e)
        if "403" in msg:
            return {"status": "blocked", "http_status": 403, "url": url, "detail": msg}
        if "429" in msg:
            return {"status": "blocked", "http_status": 429, "url": url, "detail": msg}
        return {"status": "error", "http_status": None, "url": url, "detail": msg}
    return {"status": "ok", "http_status": 200, "url": url}
