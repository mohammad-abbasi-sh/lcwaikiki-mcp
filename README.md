# lcwaikiki-mcp

Unofficial read-only MCP server for **LC Waikiki** (lcw.com) — Türkiye's biggest fashion retailer (1,300+ stores, founded 1988): product search, full product detail, the category directory, one category's products and price statistics.

mcp-name: io.github.mohammad-abbasi-sh/lcwaikiki-mcp

## Tools

| Tool | What it does |
| --- | --- |
| `lcwaikiki_search_products` | Search products by keyword (Turkish), e.g. `elbise` (dress), `kot pantolon`, `kaban`. Page (100 products/page), sort: `default`, `price_asc`, `price_desc`, `newest`, `discount`, `best_sellers`, `most_reviewed`, `most_favorited`. |
| `lcwaikiki_get_product` | Full detail of one product (URL or path with `-o-<id>`): name, brand, colour, sizes, material, fabric, price in TRY, stock status, shipping, aggregate rating, review count and up to 5 recent reviews. |
| `lcwaikiki_list_categories` | The full category directory: 6 departments (KADIN, ERKEK, ÇOCUK, BEBEK, EV \| YAŞAM, Fırsat Alanı), groups and 185 categories with URLs and tree ids. |
| `lcwaikiki_category_products` | Products of one category (e.g. `/kadin-giyim-t-10`), with paging and the same sorts as search. |
| `lcwaikiki_price_stats` | Price statistics for a search (first 100 results): min / median / mean / max in TRY, discounted share, average discount, average rating, top brands. |
| `lcwaikiki_health` | Reachability check (home page + one search). |

## Install

Requires Python 3.10+. The package is published on PyPI (pending publisher setup — see below); once live:

```bash
uvx lcwaikiki-mcp
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lcwaikiki": {
      "command": "uvx",
      "args": ["lcwaikiki-mcp"]
    }
  }
}
```

No login, no API key. Read-only: the server only fetches public pages.

## For AI agents

- Search is Turkish: use Turkish keywords (`elbise`, not `dress`). Results carry `exact_match` — when the site finds nothing it returns `exact_match: false` with generic fallback products; check the flag before treating results as matches.
- Prices are live and move with campaigns; `old_price_try` is the site's listed old price and `discount_pct` is computed from it. Verify price and availability on lcw.com before buying.
- A product URL always ends in `-o-<id>` (e.g. `...-elbise-haki-o-5657836`) — that is the identifier `lcwaikiki_get_product` needs.
- Category ids come from `lcwaikiki_list_categories` (e.g. Kadın Giyim is `/kadin-giyim-t-10`).
- Every response includes `fetched_at` (UTC) and `source`.

## How it works

- Search and category listings are parsed from the server-rendered pages (100 products per page, `catalogModel` JSON embedded in the HTML). The product-list AJAX endpoint (`/tr/ajax/ProductList/ProductListPageData`) exists but reports pre-campaign prices that disagree with the product pages (same dress: 989.99 via AJAX, 649.99 on its detail page), returns only a generic 52-item fallback for categories from a stateless request, and hangs on Akamai when called inside a session — so listings use HTML.
- Detail pages are parsed from the schema.org `Product` JSON-LD block plus the fabric data in the page's `Option()` call.
- Transport uses Chrome TLS impersonation (curl-cffi): plain requests are refused with HTTP 403 (Akamai). Requests are spaced ~0.8s apart and retried once with another fingerprint on 403/429.

## Caveats

- LC Waikiki runs frequent campaigns: a price seen in the morning can change the same day. The server always returns what the site returns at fetch time.
- Review text is unfiltered user-generated content (Turkish).
- The site's own Firebase web key embedded in recorded pages was scrubbed from the test fixtures before publishing.

## License

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — free for personal and non-commercial use; commercial use needs a separate license.

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
