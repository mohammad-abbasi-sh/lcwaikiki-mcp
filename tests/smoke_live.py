"""Daily smoke probe (CI): search + one product + categories + health.

Run with:  python tests/smoke_live.py
Exit 0 = site reachable, exit 1 = blocked/error (visible in CI).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lcwaikiki_mcp.server import (  # noqa: E402
    lcwaikiki_get_product,
    lcwaikiki_health,
    lcwaikiki_list_categories,
    lcwaikiki_search_products,
)


def main() -> int:
    try:
        res = json.loads(lcwaikiki_search_products("elbise", limit=5))
        assert "error" not in res, res.get("error")
        assert res["exact_match"] is True
        assert res["count"] == 5
        assert res["total"] > 1000
        pr = json.loads(
            lcwaikiki_get_product(res["products"][0]["url"])
        )
        assert "error" not in pr, pr.get("error")
        assert pr["price_try"] > 0
        cats = json.loads(lcwaikiki_list_categories())
        assert "error" not in cats, cats.get("error")
        assert cats["total"] >= 100
        health = json.loads(lcwaikiki_health())
        assert health["status"] == "ok", health
        print(
            f"SMOKE OK: search elbise total={res['total']} | "
            f"product={pr['name'][:50]} {pr['price_try']} TRY | "
            f"categories={cats['total']}"
        )
        return 0
    except Exception as e:  # noqa: BLE001 — smoke must report, not crash
        print(f"SMOKE FAIL: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
