"""Offline tests for lcwaikiki_mcp parsers (recorded fixtures, no network).

Fixtures (recorded 2026-11-22 from www.lcw.com):
- search-elbise.json — product-list AJAX JSON, q=elbise page 1
  (100 products, total 12,910, 130 pages)
- search-elbise.html — the server-rendered search page for q=elbise
  (same query, recorded ~20 min earlier — its first product is still
  priced 649.99 while the JSON fixture has 989.99; LCW prices move
  with campaigns, so tests assert each fixture's own values)
- search-noresults.json — AJAX JSON for q=zzzzqqq (ProductFound false,
  52 generic fallback products)
- category-kadin-giyim.html — the catalogModel script from the
  server-rendered /kadin-giyim-t-10 page (24,469 items, 245 pages,
  101 products on page 1). Categories are parsed from HTML, not the
  AJAX endpoint: a stateless AJAX call with CategoryTreeId returns
  only the site's 52-item generic fallback (verified live 2026-11-22
  for ids 10 and 45), and a session-based call hangs on Akamai.
- product-5657836.html — "Çiçekli Kız Çocuk Kadife Elbise" detail page
  (Product JSON-LD + Option() fabric data; the site's own Firebase
  apiKey in the page was scrubbed to REDACTED)
- all-categories.html — the <nav class="menu-nav"> mega-menu block
  from /tum-kategoriler-u-6000009 (6 departments, 185 categories)

Run with:  python -m pytest tests/test_parse.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lcwaikiki_mcp import parse as P  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


# --- prices -----------------------------------------------------------------

def test_parse_tr_price():
    assert P.parse_tr_price("1.099,99 TL") == 1099.99
    assert P.parse_tr_price("989,99 TL") == 989.99
    assert P.parse_tr_price("649.99") == 649.99
    assert P.parse_tr_price(None) is None
    assert P.parse_tr_price("") is None


# --- search JSON ------------------------------------------------------------

def test_search_json_counts():
    res = P.parse_search_json(_read("search-elbise.json"))
    assert res["query"] == "elbise"
    assert res["exact_match"] is True
    assert res["total"] == 12910
    assert res["page"] == 1
    assert res["page_count"] == 130
    assert len(res["products"]) == 100


def test_search_json_first_product():
    res = P.parse_search_json(_read("search-elbise.json"))
    p = res["products"][0]
    assert p["option_id"] == 5657836
    assert p["model_id"] == 15632194
    assert p["name"] == "Çiçekli Kız Çocuk Kadife Elbise"
    assert p["brand"] == "LCW KIDS"
    assert p["gender"] == "Kız Çocuk"
    assert p["category"] == "Çocuk > Giyim > Elbise-Kız Çocuk > Elbise"
    assert p["price_try"] == 989.99
    assert p["old_price_try"] == 1099.99
    assert p["discount_pct"] == 10.0
    assert p["rating"] == 3.82
    assert p["review_count"] == 11
    assert p["stock"] == 1766
    assert p["code"] == "W6JU86Z1-1Y2"
    assert p["url"] == (
        "https://www.lcw.com/cicekli-kiz-cocuk-kadife-elbise-haki-o-5657836"
    )
    assert p["image"].startswith("https://img-lcwaikiki.mncdn.com/")


def test_search_json_no_results_fallback():
    res = P.parse_search_json(_read("search-noresults.json"))
    assert res["query"] == "zzzzqqq"
    assert res["exact_match"] is False
    assert res["total"] == 52
    assert len(res["products"]) == 52
    assert res["products"][0]["name"] == "Winnie the Pooh Baskılı Kahve Fincan Takımı"


def test_search_json_bad_input():
    for bad in ("<not json", '{"nope": 1}', ""):
        try:
            P.parse_search_json(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


# --- search HTML ------------------------------------------------------------

def test_search_html_same_model():
    res = P.parse_search_html(_read("search-elbise.html"))
    assert res["query"] == "elbise"
    assert res["exact_match"] is True
    assert res["total"] == 12910
    assert len(res["products"]) == 100
    p = res["products"][0]
    assert p["name"] == "Çiçekli Kız Çocuk Kadife Elbise"
    # this recording predates the JSON fixture: campaign price was lower
    assert p["price_try"] == 649.99
    assert p["old_price_try"] == 1099.99


def test_extract_catalog_model_missing():
    try:
        P.extract_catalog_model("<html><body>no model here</body></html>")
    except ValueError:
        return
    raise AssertionError("expected ValueError for missing catalogModel")


# --- category HTML ----------------------------------------------------------

def test_category_html():
    res = P.parse_category_html(
        _read("category-kadin-giyim.html"), "/kadin-giyim-t-10"
    )
    assert res["category"] == "Kadın > Kadın Giyim"
    assert res["category_url"] == "https://www.lcw.com/kadin-giyim-t-10"
    assert res["total"] == 24469
    assert res["page"] == 1
    assert res["page_count"] == 245
    assert len(res["products"]) == 101
    first = res["products"][0]
    assert first["name"] == "Beli Lastikli Soft Touch Kadın Eşofman Altı"
    assert first["price_try"] == 799.99
    assert first["brand"] == "LCW VISION"
    assert "exact_match" not in res  # meaningless for categories


def test_resolve_category():
    assert P.resolve_category("kadin-giyim-t-10") == (10, "/kadin-giyim-t-10")
    assert P.resolve_category("/kadin-giyim-t-10") == (10, "/kadin-giyim-t-10")
    assert P.resolve_category("https://www.lcw.com/kadin-elbise-t-149") == (
        149,
        "/kadin-elbise-t-149",
    )
    for bad in ("kadin-giyim", "https://example.com/kadin-giyim-t-10", ""):
        try:
            P.resolve_category(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


# --- product detail ---------------------------------------------------------

def test_product_page():
    url = "https://www.lcw.com/cicekli-kiz-cocuk-kadife-elbise-haki-o-5657836"
    pr = P.parse_product_page(_read("product-5657836.html"), url)
    assert pr["name"] == "Çiçekli Kız Çocuk Kadife Elbise"
    assert pr["sku"] == "W6JU86Z1"
    assert pr["brand"] == "LCW KIDS"
    assert pr["color"] == "Haki"
    assert "1-2 Yaş" in pr["sizes"] and len(pr["sizes"]) == 7
    assert pr["material"] == ["Kadife"]
    assert pr["fabric"] == "Ana Kumaş: %100 Pamuk"
    assert pr["price_try"] == 649.99
    assert pr["currency"] == "TRY"
    assert pr["availability"] == "InStock"
    assert pr["shipping_try"] == 79.99
    assert pr["rating"] == 3.8
    assert pr["review_count"] == 11
    assert len(pr["reviews"]) == 5
    assert pr["reviews"][0]["author"] == "ö**** k***"
    assert pr["reviews"][0]["rating"] == 4.0
    assert pr["reviews"][0]["text"].startswith("kalıbı")
    assert pr["properties"]["Menşei"] == "Türkiye"
    assert pr["properties"]["Kumaş"] == "Kadife"
    assert len(pr["images"]) == 4
    assert pr["category"].startswith("Bebek > Bebek Giyim")


def test_product_page_no_json_ld():
    try:
        P.parse_product_page("<html><body>no ld+json</body></html>", "https://x/")
    except ValueError:
        return
    raise AssertionError("expected ValueError for missing Product JSON-LD")


# --- categories -------------------------------------------------------------

def test_categories_departments():
    cats = P.parse_categories(_read("all-categories.html"))
    names = [d["name"] for d in cats["departments"]]
    assert names == ["KADIN", "ERKEK", "ÇOCUK", "BEBEK", "EV | YAŞAM", "Fırsat Alanı"]
    assert cats["total"] == 185


def test_categories_kadin_giyim():
    cats = P.parse_categories(_read("all-categories.html"))
    kadin = cats["departments"][0]
    giyim = kadin["groups"][0]
    assert giyim["title"] == "GİYİM"
    assert giyim["id"] == 10
    assert giyim["url"] == "https://www.lcw.com/kadin-giyim-t-10"
    first = giyim["categories"][0]
    assert first["name"] == "Mont | Kaban"
    assert first["id"] == 9867
    assert first["url"] == "https://www.lcw.com/kadin-dis-giyim-t-9867"
    # campaign links and "TÜMÜNÜ GÖR" rows are dropped
    assert all(c["id"] is not None for g in kadin["groups"] for c in g["categories"])
    assert not any(
        "kampanyalar" in c["url"] for g in kadin["groups"] for c in g["categories"]
    )


def test_categories_no_nav():
    try:
        P.parse_categories("<html><body>no nav</body></html>")
    except ValueError:
        return
    raise AssertionError("expected ValueError for missing menu nav")
