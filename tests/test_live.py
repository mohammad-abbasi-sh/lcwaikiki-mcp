"""Live tests for lcwaikiki_mcp (real network, read-only).

Run with:  python -m pytest tests/test_live.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lcwaikiki_mcp.server import (  # noqa: E402
    lcwaikiki_category_products,
    lcwaikiki_get_product,
    lcwaikiki_health,
    lcwaikiki_list_categories,
    lcwaikiki_price_stats,
    lcwaikiki_search_products,
)

_PRODUCT_URL = (
    "https://www.lcw.com/cicekli-kiz-cocuk-kadife-elbise-haki-o-5657836"
)


def test_live_search():
    res = json.loads(lcwaikiki_search_products("elbise", limit=10))
    assert "error" not in res, res.get("error")
    assert res["exact_match"] is True
    assert res["total"] > 1000
    assert res["count"] == 10
    assert res["products"][0]["name"]
    assert res["products"][0]["price_try"] > 0
    assert res["products"][0]["url"].startswith("https://www.lcw.com/")


def test_live_search_price_asc():
    res = json.loads(lcwaikiki_search_products("elbise", sort="price_asc", limit=5))
    assert "error" not in res, res.get("error")
    prices = [p["price_try"] for p in res["products"]]
    assert prices == sorted(prices)


def test_live_search_page_2():
    res = json.loads(lcwaikiki_search_products("elbise", page=2, limit=5))
    assert "error" not in res, res.get("error")
    assert res["page"] == 2
    assert res["count"] == 5


def test_live_search_no_results():
    res = json.loads(lcwaikiki_search_products("zzzzqqq", limit=5))
    assert "error" not in res, res.get("error")
    assert res["exact_match"] is False


def test_live_search_bad_sort():
    res = json.loads(lcwaikiki_search_products("elbise", sort="nope"))
    assert "error" in res


def test_live_get_product():
    pr = json.loads(lcwaikiki_get_product(_PRODUCT_URL))
    assert "error" not in pr, pr.get("error")
    assert "Elbise" in pr["name"]
    assert pr["sku"] == "W6JU86Z1"
    assert pr["price_try"] > 0
    assert pr["currency"] == "TRY"
    assert len(pr["sizes"]) >= 1
    assert pr["rating"] is not None
    assert pr["review_count"] >= 0


def test_live_get_product_bad_url():
    pr = json.loads(lcwaikiki_get_product("https://example.com/foo"))
    assert "error" in pr


def test_live_category_products():
    res = json.loads(lcwaikiki_category_products("kadin-giyim-t-10", limit=5))
    assert "error" not in res, res.get("error")
    assert res["category"] == "Kadın > Kadın Giyim"
    assert res["total"] > 100
    assert res["count"] == 5


def test_live_category_products_bad():
    res = json.loads(lcwaikiki_category_products("not-a-category"))
    assert "error" in res


def test_live_list_categories():
    cats = json.loads(lcwaikiki_list_categories())
    assert "error" not in cats, cats.get("error")
    assert cats["total"] >= 100
    names = [d["name"] for d in cats["departments"]]
    assert "KADIN" in names and "ERKEK" in names and "BEBEK" in names


def test_live_price_stats():
    stats = json.loads(lcwaikiki_price_stats("elbise"))
    assert "error" not in stats, stats.get("error")
    assert stats["exact_match"] is True
    assert stats["total"] > 1000
    assert stats["analysed"] == 100
    assert stats["min_try"] > 0
    assert stats["min_try"] <= stats["median_try"] <= stats["max_try"]
    assert stats["top_brands"]


def test_live_health():
    health = json.loads(lcwaikiki_health())
    assert health["status"] == "ok", health
