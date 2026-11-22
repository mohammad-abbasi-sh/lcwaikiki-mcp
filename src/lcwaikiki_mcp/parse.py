"""Parsers for lcwaikiki_mcp — LC Waikiki product-list JSON, product
JSON-LD and the all-categories mega-menu. Stdlib only.
"""
from __future__ import annotations

import html as _html
import json
import re
from urllib.parse import urlparse

BASE = "https://www.lcw.com"

# --- generic helpers -------------------------------------------------------

_TR_PRICE_RE = re.compile(r"([\d.]+,\d+|\d+(?:\.\d+)?)")


def parse_tr_price(text: str | None) -> float | None:
    """Parse a Turkish price string ("1.099,99 TL", "989,99 TL") to float.

    Returns None for empty/None input. Raises ValueError on garbage.
    """
    if not text:
        return None
    m = _TR_PRICE_RE.search(str(text).replace("\xa0", " ").strip())
    if not m:
        return None
    raw = m.group(1)
    if "," in raw:  # Turkish: dot = thousands, comma = decimal
        return float(raw.replace(".", "").replace(",", "."))
    return float(raw)


def _strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


def _extract_braced_json(text: str, start_marker: str) -> str:
    """Extract the {...} JSON object following start_marker, brace-aware.

    Handles braces inside double-quoted strings and backslash escapes.
    Raises ValueError when the marker or a balanced object is missing.
    """
    i = text.find(start_marker)
    if i < 0:
        raise ValueError(f"marker not found: {start_marker!r}")
    j = text.find("{", i)
    if j < 0:
        raise ValueError(f"no JSON object after marker: {start_marker!r}")
    depth = 0
    instr = False
    esc = False
    k = j
    while k < len(text):
        c = text[k]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[j : k + 1]
        k += 1
    raise ValueError(f"unbalanced JSON object after marker: {start_marker!r}")


def extract_catalog_model(html: str) -> dict:
    """The `var catalogModel = {...};` blob on search/category pages."""
    raw = _extract_braced_json(html, "var catalogModel")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"catalogModel is not valid JSON: {e}") from e


# --- search / category listings --------------------------------------------

def _summarize_item(item: dict) -> dict:
    old_price = parse_tr_price(item.get("OldPrice"))
    price = item.get("PriceValue")
    try:
        price = float(price) if price is not None else None
    except (TypeError, ValueError):
        price = None
    discount_pct = None
    if price is not None and old_price is not None and old_price > price:
        discount_pct = round((old_price - price) / old_price * 100, 1)
    crumb = item.get("BreadCrump") or {}
    levels = [crumb.get(f"Level{i}") for i in (1, 2, 3, 4)]
    category = " > ".join(x for x in levels if x) or None
    rating = item.get("AvgScore")
    try:
        rating = float(rating) if rating is not None else None
    except (TypeError, ValueError):
        rating = None
    return {
        "option_id": item.get("OptionId"),
        "model_id": item.get("ModelId"),
        "name": item.get("ProductDescription"),
        "brand": item.get("Brand"),
        "gender": item.get("Gender"),
        "category": category,
        "price_try": price,
        "old_price_try": old_price,
        "discount_pct": discount_pct,
        "rating": rating,
        "review_count": item.get("ReviewCount"),
        "stock": item.get("AvailableStock"),
        "code": item.get("OzelKodRenkKod"),
        "color_hex": item.get("MainColorHexCode"),
        "is_outlet": bool(item.get("IsOutlet")),
        "url": BASE + item["ModelUrl"] if item.get("ModelUrl") else None,
        "image": item.get("DefaultOptionImageUrl"),
    }


def _listing_common(catalog: dict) -> dict:
    cl = catalog.get("CatalogList") or {}
    pv = catalog.get("PageView") or {}
    items = cl.get("Items") or []
    return {
        "exact_match": bool(catalog.get("ProductFound")),
        "total": cl.get("ItemCount") if cl.get("ItemCount") is not None else len(items),
        "page": catalog.get("PageIndex") or cl.get("PageIndex") or 1,
        "page_count": cl.get("PageCount") or pv.get("PageCount") or 1,
        "products": [_summarize_item(i) for i in items],
    }


def _from_catalog(catalog: dict) -> dict:
    out = _listing_common(catalog)
    out["query"] = catalog.get("Query") or catalog.get("SearchKey")
    return out


def parse_search_json(text: str) -> dict:
    """Parse the product-list AJAX JSON for a search.

    Returns query, exact_match (False when the site found nothing and
    returned its generic fallback products), total, page, page_count
    and the product summaries. Raises ValueError on bad JSON.

    NOTE: the live server does NOT use this path — the AJAX endpoint
    reports pre-campaign prices that disagree with the product pages
    (see http.fetch_search_html). Kept for the recorded fixture and
    for callers that already hold the JSON.
    """
    try:
        catalog = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"search response is not valid JSON: {e}") from e
    if not isinstance(catalog, dict) or "CatalogList" not in catalog:
        raise ValueError("search response has no CatalogList")
    return _from_catalog(catalog)


def _breadcrumb_path(nodes: list, target_url: str | None) -> str | None:
    """Walk BreadcrumbList to the node matching target_url ("/x-t-45").

    Returns "Parent > Child" or the root text when the target is the
    root itself; None when the tree is empty.
    """
    def walk(node: dict, path: list[str]) -> list[str] | None:
        name = node.get("BreadCrumbTextKeyword")
        url = (node.get("Url") or "").strip()
        here = path + ([name] if name else [])
        if target_url and url == target_url:
            return here
        for child in node.get("ChildCategories") or []:
            hit = walk(child, here)
            if hit:
                return hit
        return None

    for node in nodes or []:
        hit = walk(node, [])
        if hit:
            return " > ".join(hit)
    # fall back to the root node's text
    if nodes and nodes[0].get("BreadCrumbTextKeyword"):
        return nodes[0]["BreadCrumbTextKeyword"]
    return None


def parse_category_json(text: str, category_url: str | None = None) -> dict:
    """Parse the product-list AJAX JSON for one category (by tree id).

    NOTE: only useful for responses the site itself produced for a
    category page load; a stateless AJAX call with CategoryTreeId
    returns the generic fallback — see http.fetch_category_html.
    """
    try:
        catalog = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"category response is not valid JSON: {e}") from e
    if not isinstance(catalog, dict) or "CatalogList" not in catalog:
        raise ValueError("category response has no CatalogList")
    out = _listing_common(catalog)
    out.pop("exact_match", None)  # meaningless for categories
    out["category"] = _breadcrumb_path(catalog.get("BreadcrumbList"), category_url)
    out["category_url"] = (
        BASE + category_url if category_url and category_url.startswith("/") else category_url
    )
    return out


def parse_search_html(html: str) -> dict:
    """Parse a server-rendered search page (same model, HTML form).

    This is the path the live server uses — its prices match the
    product detail pages, unlike the AJAX endpoint's.
    """
    return _from_catalog(extract_catalog_model(html))


def parse_category_html(html: str, category_url: str | None = None) -> dict:
    """Parse a server-rendered category page (same model, HTML form)."""
    catalog = extract_catalog_model(html)
    out = _listing_common(catalog)
    out.pop("exact_match", None)  # meaningless for categories
    out["category"] = _breadcrumb_path(catalog.get("BreadcrumbList"), category_url)
    out["category_url"] = (
        BASE + category_url if category_url and category_url.startswith("/") else category_url
    )
    return out


# --- product detail ----------------------------------------------------------

_LD_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S
)
_OPTION_RE = re.compile(
    r"new Option\(\d+,'[^']*', '[^']*', '(.*?)', \d+\)", re.S
)


def parse_product_page(html: str, url: str) -> dict:
    """Parse a product detail page via its schema.org Product JSON-LD.

    Returns name, brand, category path, price, sizes, colours, fabric,
    rating + a few recent reviews, shipping and return info.
    Raises ValueError when no Product block is found.
    """
    product = None
    breadcrumbs = None
    for m in _LD_RE.finditer(html):
        try:
            block = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(block, dict) and block.get("@type") == "Product":
            product = block
        elif isinstance(block, dict) and block.get("@type") == "BreadcrumbList":
            breadcrumbs = block
    if product is None:
        raise ValueError("no Product JSON-LD found on the product page")

    offers = product.get("offers") or {}
    rating = product.get("aggregateRating") or {}
    reviews = []
    for r in product.get("review") or []:
        rr = r.get("reviewRating") or {}
        author = r.get("author") or {}
        reviews.append(
            {
                "author": author.get("name"),
                "date": r.get("datePublished"),
                "rating": rr.get("ratingValue"),
                "text": r.get("reviewBody"),
            }
        )
    props = {}
    for p in product.get("additionalProperty") or []:
        if p.get("name") and p.get("value") is not None:
            props[p["name"]] = p["value"]
    # fabric / composition: the Option() JS call carries an HTML list
    fabric = None
    om = _OPTION_RE.search(html)
    if om:
        fabric = _strip_tags(om.group(1)) or None
    cat_path = None
    if breadcrumbs:
        names = [
            el.get("name")
            for el in breadcrumbs.get("itemListElement") or []
            if el.get("name") and el.get("name") != "Ana Sayfa"
        ]
        cat_path = " > ".join(names) if names else None
    if not cat_path:
        cat_path = product.get("category")
    shipping = (offers.get("shippingDetails") or {}).get("shippingRate") or {}
    return {
        "name": product.get("name"),
        "url": url,
        "sku": product.get("sku"),
        "gtin13": product.get("gtin13"),
        "brand": (product.get("brand") or {}).get("name"),
        "category": cat_path,
        "description": product.get("description"),
        "color": product.get("color"),
        "sizes": product.get("size") or [],
        "material": product.get("material") or [],
        "fabric": fabric,
        "properties": props,
        "price_try": parse_tr_price(str(offers.get("price"))) if offers.get("price") is not None else None,
        "currency": offers.get("priceCurrency"),
        "availability": (offers.get("availability") or "").rsplit("/", 1)[-1] or None,
        "shipping_try": parse_tr_price(str(shipping.get("value"))) if shipping.get("value") is not None else None,
        "rating": rating.get("ratingValue"),
        "review_count": rating.get("reviewCount"),
        "reviews": reviews[:5],
        "images": product.get("image") or [],
    }


# --- categories --------------------------------------------------------------

_CAT_ID_RE = re.compile(r"-t-(\d+)(?:[/?#]|$)")
_DEPT_RE = re.compile(
    r'<li class="menu-header-item">\s*<a[^>]*class="menu-header-item__title"[^>]*>(.*?)</a>(.*?)(?=<li class="menu-header-item">|\Z)',
    re.S,
)
_GROUP_RE = re.compile(
    r'<li class="zone-header">\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>\s*</li>(.*?)(?=<li class="zone-header">|\Z)',
    re.S,
)
_ITEM_RE = re.compile(
    r'<li class="zone-item">\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S
)


def _extract_menu_nav(html: str) -> str:
    """Extract the <nav class="menu-nav">…</nav> block, depth-counted.

    The mega-menu nests a second <nav class="nav-tab"> inside the
    ÇOCUK department, so a non-greedy regex would stop at the inner
    </nav> and cut the remaining departments off.
    """
    start = html.find('<nav class="menu-nav">')
    if start < 0:
        raise ValueError("menu navigation not found on the categories page")
    depth = 0
    for m in re.finditer(r"<nav\b|</nav>", html[start:]):
        if m.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return html[start : start + m.end()]
        else:
            depth += 1
    raise ValueError("unbalanced <nav> in the categories page")


def resolve_category(value: str) -> tuple[int, str]:
    """Resolve a category reference to (tree id, site path).

    Accepts a full lcw.com URL, a site path ("/kadin-giyim-t-10") or a
    bare slug ("kadin-giyim-t-10"). Raises ValueError otherwise.
    """
    v = (value or "").strip()
    if v.startswith("http"):
        parsed = urlparse(v)
        if "lcw.com" not in parsed.netloc and "lcwaikiki.com" not in parsed.netloc:
            raise ValueError("category must be an lcw.com / lcwaikiki.com URL or path")
        v = parsed.path
    if not v.startswith("/"):
        v = "/" + v
    m = _CAT_ID_RE.search(v)
    if not m:
        raise ValueError(
            "category must look like '/kadin-giyim-t-10' (find one with "
            "lcwaikiki_list_categories first)"
        )
    return int(m.group(1)), v


def parse_categories(html: str) -> dict:
    """Parse the all-categories page's mega-menu into departments.

    Returns {"departments": [{"name": "KADIN", "groups": [{"title":
    "GİYİM", "categories": [{"name", "url", "id"}]}]}], "total": N}.
    Only real category links ("/…-t-<id>") are kept — the menu also
    carries campaign links ("/kampanyalar/…") and "TÜMÜNÜ GÖR" rows,
    which are dropped. Raises ValueError when the navigation block is
    missing.
    """
    nav = _extract_menu_nav(html)
    departments = []
    total = 0
    for dm in _DEPT_RE.finditer(nav):
        dept_name = _strip_tags(dm.group(1))
        body = dm.group(2)
        groups = []
        for gm in _GROUP_RE.finditer(body):
            group_url, group_title, gbody = gm.group(1), gm.group(2), gm.group(3)
            cats = []
            for im in _ITEM_RE.finditer(gbody):
                url, name = im.group(1), _strip_tags(im.group(2))
                if name.upper() in ("TÜMÜNÜ GÖR", "TUMUNU GOR"):
                    continue
                idm = _CAT_ID_RE.search(url)
                if not idm:
                    continue  # campaign link, not a category
                cats.append(
                    {
                        "name": name,
                        "url": BASE + url if url.startswith("/") else url,
                        "id": int(idm.group(1)),
                    }
                )
            if not cats:
                continue  # campaign-only group, e.g. "BAMBAŞKA İNDİRİM"
            gid = _CAT_ID_RE.search(group_url)
            groups.append(
                {
                    "title": _strip_tags(group_title),
                    "url": BASE + group_url if group_url.startswith("/") else group_url,
                    "id": int(gid.group(1)) if gid else None,
                    "categories": cats,
                }
            )
            total += len(cats)
        if groups:
            departments.append({"name": dept_name, "groups": groups})
    if not departments:
        raise ValueError("no departments found on the categories page")
    return {"departments": departments, "total": total}
