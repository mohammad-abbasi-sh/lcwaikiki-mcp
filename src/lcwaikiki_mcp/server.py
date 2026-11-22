"""MCP server: unofficial read-only access to LC Waikiki (lcw.com) —
Türkiye's biggest fashion retailer: product search, product detail,
category listings, price statistics and the category directory."""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from . import http as _http
from . import parse as _P

mcp = FastMCP("lcwaikiki-mcp")

INSTRUCTIONS = """\
Unofficial read-only MCP server for LC Waikiki (www.lcw.com) — \
Türkiye's biggest fashion retailer (1,300+ stores, founded 1988): \
product search (lcwaikiki_search_products), full product detail \
with sizes, fabric, ratings and reviews \
(lcwaikiki_get_product), the category directory \
(lcwaikiki_list_categories), one category's products \
(lcwaikiki_category_products) and price statistics over a search \
(lcwaikiki_price_stats). Search and category listings are parsed \
from the server-rendered pages (100 products per page): the \
product-list AJAX endpoint reports pre-campaign prices that \
disagree with the product pages, and returns only a generic \
fallback for categories, so listings use HTML. Sorts: relevance, \
price asc/desc, newest, biggest discount, best sellers, most \
reviewed, most favourited. Detail pages are parsed from the \
schema.org Product block (price, sizes, material, aggregate rating, \
recent reviews, shipping and returns). A nonsense query returns \
exact_match=false with no products (the site 404s it) — check that \
flag before treating results as matches. \
Prices are live and can move with campaigns; the old price is the \
site's listed one and discount_pct is computed from it. No login, \
no API key. Read-only; transport uses Chrome TLS impersonation \
(plain requests are refused with HTTP 403); requests are spaced \
~0.8s apart. Built by Mohammad Abbasi (mohammad-abbasi-sh) — \
https://almanibama.ir · https://mabbasi.ir — Turkey MCP factory.\
"""

_SOURCE = "www.lcw.com"
_DISCLAIMER = (
    "Unofficial read-only LC Waikiki data from the site's public pages "
    "and product-list endpoint; verify prices and availability on the "
    "official site before buying — prices move with campaigns."
)

_SORTS = {
    "default": None,
    "price_asc": "PriceASC",
    "price_desc": "PriceDESC",
    "newest": "CreateDateDESC",
    "discount": "NewDiscountedPriceByDateDESC",
    "best_sellers": "SaleQuantitySort",
    "most_reviewed": "ReviewCountSort",
    "most_favorited": "FavoriteQuantitySort",
}


def _envelope() -> dict:
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": _SOURCE,
        "disclaimer": _DISCLAIMER,
    }


def _ok(payload: dict) -> str:
    return json.dumps({**_envelope(), **payload}, ensure_ascii=False)


def _err(e: Exception) -> str:
    return _ok({"error": str(e)})


def _limit(limit: int) -> int:
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    return max(1, min(limit, 50))


def _page(page: int) -> int:
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    return max(1, page)


def _sort(sort: str) -> str | None:
    key = (sort or "default").strip().lower()
    if key not in _SORTS:
        raise ValueError(
            f"unknown sort {sort!r}; use one of: {', '.join(_SORTS)}"
        )
    return _SORTS[key]


@mcp.tool()
def lcwaikiki_search_products(
    query: str, page: int = 1, sort: str = "default", limit: int = 10
) -> str:
    """Search LC Waikiki products by keyword (Turkish).

    query: e.g. "elbise" (dress), "kot pantolon", "kaban". page: result
    page (100 products per page, default 1). sort: default (relevance),
    price_asc, price_desc, newest, discount (biggest discount first),
    best_sellers, most_reviewed, most_favorited. limit: how many of the
    page to return (1-50, default 10). Returns each product's name,
    brand, gender, category, current and old price in TRY, computed
    discount %, rating, review count, stock and URL. When the site
    finds nothing it returns exact_match=false with no products (the
    site 404s a no-match search) — check that flag."""
    try:
        query = (query or "").strip()
        if not query:
            raise ValueError("query must not be empty")
        raw = _http.fetch_search_html(query, _sort(sort), _page(page))
        if raw is None:
            return _ok(
                {
                    "query": query,
                    "exact_match": False,
                    "total": 0,
                    "page": _page(page),
                    "page_count": 0,
                    "count": 0,
                    "products": [],
                    "note": "no products matched this query on lcw.com",
                }
            )
        res = _P.parse_search_html(raw)
        res["products"] = res["products"][: _limit(limit)]
        res["count"] = len(res["products"])
        return _ok(res)
    except (ValueError, _http.LcwaikikiError) as e:
        return _err(e)


@mcp.tool()
def lcwaikiki_get_product(product: str) -> str:
    """Full detail of one LC Waikiki product.

    product: a full lcw.com product URL or site path, e.g.
    "https://www.lcw.com/cicekli-kiz-cocuk-kadife-elbise-haki-o-5657836"
    (the "-o-<id>" suffix identifies the product — find one with
    lcwaikiki_search_products first). Returns name, brand, category,
    SKU, colour, available sizes, material, fabric composition,
    current price in TRY, stock status, shipping cost, aggregate
    rating, review count, up to 5 recent reviews and image URLs."""
    try:
        value = (product or "").strip()
        if not value:
            raise ValueError("product must not be empty")
        page = _http.fetch_product_html(value)
        url = value if value.startswith("http") else _P.BASE + (
            value if value.startswith("/") else "/" + value
        )
        return _ok(_P.parse_product_page(page, url))
    except (ValueError, _http.LcwaikikiError) as e:
        return _err(e)


@mcp.tool()
def lcwaikiki_list_categories() -> str:
    """LC Waikiki's full category directory, grouped by department.

    Returns departments (KADIN, ERKEK, ÇOCUK, BEBEK, EV & YAŞAM, ...)
    with their groups (GİYİM, AYAKKABI, AKSESUAR, ...) and categories,
    each with its Turkish name, URL and numeric tree id. Use a
    category's URL or id with lcwaikiki_category_products. No
    arguments."""
    try:
        cats = _P.parse_categories(_http.fetch_all_categories_html())
        return _ok(cats)
    except (ValueError, _http.LcwaikikiError) as e:
        return _err(e)


@mcp.tool()
def lcwaikiki_category_products(
    category: str, page: int = 1, sort: str = "default", limit: int = 10
) -> str:
    """Products of one LC Waikiki category.

    category: a category URL, site path or slug from
    lcwaikiki_list_categories, e.g. "/kadin-giyim-t-10" or
    "kadin-elbise-t-149". page: result page (100 products per page,
    default 1). sort: default, price_asc, price_desc, newest,
    discount, best_sellers, most_reviewed, most_favorited. limit:
    how many of the page to return (1-50, default 10)."""
    try:
        _cid, path = _P.resolve_category(category)
        raw = _http.fetch_category_html(path, _sort(sort), _page(page))
        res = _P.parse_category_html(raw, path)
        res["products"] = res["products"][: _limit(limit)]
        res["count"] = len(res["products"])
        return _ok(res)
    except (ValueError, _http.LcwaikikiError) as e:
        return _err(e)


@mcp.tool()
def lcwaikiki_price_stats(query: str) -> str:
    """Price statistics for an LC Waikiki search (first 100 results).

    query: e.g. "elbise". Returns the search total, the number of
    products analysed, min / median / mean / max price in TRY, how
    many are discounted and the average discount, the average rating,
    and the most common brands. Use it to answer "how much does X
    cost at LCW?" without paging through listings."""
    try:
        query = (query or "").strip()
        if not query:
            raise ValueError("query must not be empty")
        raw = _http.fetch_search_html(query, None, 1)
        if raw is None:
            return _ok(
                {
                    "query": query,
                    "exact_match": False,
                    "total": 0,
                    "analysed": 0,
                    "note": "no products matched this query on lcw.com",
                }
            )
        res = _P.parse_search_html(raw)
        products = res["products"]
        prices = [p["price_try"] for p in products if p["price_try"] is not None]
        if not prices:
            return _ok(
                {
                    "query": query,
                    "exact_match": res["exact_match"],
                    "total": res["total"],
                    "analysed": 0,
                    "note": "no priced products on the first page",
                }
            )
        discounted = [p for p in products if p["discount_pct"]]
        ratings = [p["rating"] for p in products if p["rating"] is not None]
        brands: dict[str, int] = {}
        for p in products:
            if p["brand"]:
                brands[p["brand"]] = brands.get(p["brand"], 0) + 1
        return _ok(
            {
                "query": query,
                "exact_match": res["exact_match"],
                "total": res["total"],
                "analysed": len(prices),
                "min_try": min(prices),
                "median_try": round(statistics.median(prices), 2),
                "mean_try": round(statistics.mean(prices), 2),
                "max_try": max(prices),
                "discounted_count": len(discounted),
                "avg_discount_pct": round(
                    statistics.mean(p["discount_pct"] for p in discounted), 1
                )
                if discounted
                else None,
                "avg_rating": round(statistics.mean(ratings), 2) if ratings else None,
                "top_brands": sorted(brands.items(), key=lambda kv: -kv[1])[:5],
                "cheapest": min(products, key=lambda p: p["price_try"] or 1e18)["name"],
                "most_expensive": max(products, key=lambda p: p["price_try"] or 0)["name"],
            }
        )
    except (ValueError, _http.LcwaikikiError) as e:
        return _err(e)


@mcp.tool()
def lcwaikiki_health() -> str:
    """Check whether LC Waikiki is reachable right now.

    Returns status ok (HTTP 200), blocked (HTTP 403/429 — bot wall or
    rate limit) or error, plus the HTTP status and the probed URL.
    Two polite requests (home page + one search); it fetches no
    product detail."""
    return _ok(_http.health_check())


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    import sys

    sys.exit(main())
