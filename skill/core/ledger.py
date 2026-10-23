"""ledger — 订单账本：导入 / 去重 / 持久化 / 损坏备份。

单一真源：schema 与幂等规则见 references/algorithms.md §四。
纪律：
  - 唯一键 orderId
  - 同 orderId 再次 ingest 只覆盖 official 快照，保留 personal，calc 重算
  - 解析失败 -> 复制到 ledger.corrupt.<ts>.json 再空态，不静默清空
  - 不存 地址 / 取餐码 / 支付号（脱敏）
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

LEDGER_VERSION = 1
DEFAULT_LEDGER = Path.home() / ".maimen-receipts" / "ledger.json"
SENSITIVE_KEYS = {
    "storeAddress", "pickupCode", "payId", "addressId", "phone",
    "mobile", "userPhone", "address", "expirePayTime",
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _dec(s: Any) -> Decimal | None:
    if s is None:
        return None
    try:
        return Decimal(str(s).strip())
    except (InvalidOperation, ValueError):
        return None


def _strip_sensitive(obj: Any) -> Any:
    """递归剔除敏感字段（脱敏）。"""
    if isinstance(obj, dict):
        return {
            k: _strip_sensitive(v)
            for k, v in obj.items()
            if k not in SENSITIVE_KEYS
        }
    if isinstance(obj, list):
        return [_strip_sensitive(x) for x in obj]
    return obj


def _mask_order_id(oid: str) -> str:
    if len(oid) <= 4:
        return "****"
    return "****" + oid[-4:]


# ---------------- 归一化 ----------------

def _normalize_order(raw: dict) -> dict:
    """把 MCP order-list / query-order 两种形状归一到 official schema。"""
    data = raw.get("data", raw)
    oid = data.get("orderId") or data.get("orderID") or ""
    if not oid:
        raise ValueError("missing orderId")

    items = []
    for p in data.get("orderProductList", []) or []:
        combo = [
            {"name": c.get("itemName") or c.get("name", ""),
             "qty": int(c.get("itemQuantity") or c.get("quantity") or 1)}
            for c in (p.get("comboItemList") or [])
        ]
        items.append({
            "name": p.get("productName") or p.get("name", ""),
            "qty": int(p.get("quantity") or 1),
            "price": str(p.get("price", "")) if p.get("price") is not None else "",
            "combo": combo,
        })

    total = _dec(data.get("totalAmount"))
    real = _dec(data.get("realTotalAmount"))
    discount = _dec(data.get("totalDiscountAmount"))
    if total is None and real is not None and discount is not None:
        total = real + discount

    official = {
        "orderId": str(oid),
        "createTime": data.get("createTime", ""),
        "storeName": data.get("storeName", ""),
        "orderStatus": data.get("orderStatus") or data.get("status", ""),
        "items": items,
        "totalAmount": str(total) if total is not None else "",
        "realTotalAmount": str(real) if real is not None else "",
        "totalDiscountAmount": str(discount) if discount is not None else "",
        "source": raw.get("source") or "mcp",
    }
    return _strip_sensitive(official)


# ---------------- 读写 ----------------

def load(path: Path) -> dict:
    """加载账本。损坏则备份后返回空态（不静默清空）。"""
    if not path.exists():
        return {"version": LEDGER_VERSION, "updated_at": _now_iso(), "orders": {}}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict) or "orders" not in obj:
            raise ValueError("invalid shape")
        return obj
    except Exception:
        backup = path.with_name(f"ledger.corrupt.{datetime.now():%Y%m%d%H%M%S}.json")
        shutil.copy2(path, backup)
        return {
            "version": LEDGER_VERSION,
            "updated_at": _now_iso(),
            "orders": {},
            "_recovered_from": str(backup),
        }


def save(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger["updated_at"] = _now_iso()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# ---------------- 动作 ----------------

def ingest(path: Path, raw: dict) -> dict:
    """导入一单。返回 {ok, order_id, added, updated, deduped, total}。

    calc 是纯派生数据（核价 + 营养），在这里算好并持久化，
    这样 `stats` 读到的 saved 立即正确，不依赖 export 先跑一遍。
    """
    official = _normalize_order(raw)
    ledger = load(path)
    oid = official["orderId"]
    existed = oid in ledger["orders"]
    entry = ledger["orders"].get(oid, {"personal": {"note": "", "tags": [], "would_reorder": None}})
    entry["official"] = official
    entry.setdefault("personal", {"note": "", "tags": [], "would_reorder": None})
    entry["calc"] = _derive_calc(official)
    entry["privacy"] = {"orderId_masked": _mask_order_id(oid)}
    ledger["orders"][oid] = entry
    save(path, ledger)
    return {
        "ok": True,
        "order_id": oid,
        "added": 0 if existed else 1,
        "updated": 1 if existed else 0,
        "deduped": existed,
        "total": len(ledger["orders"]),
        "saved": entry["calc"].get("saved"),
        "ledger": str(path),
    }


def _derive_calc(official: dict) -> dict:
    """由 official 派生 calc（核价 + 营养）。纯函数，无副作用。"""
    from pricing import audit_order
    from nutrition import compute as compute_nutrition

    calc = dict(audit_order(official))
    calc["nutrition_full"] = compute_nutrition(official.get("items", []))
    return calc


def stats(path: Path) -> dict:
    ledger = load(path)
    orders = ledger.get("orders", {})
    total = sum(_dec(o["official"].get("realTotalAmount")) or Decimal(0) for o in orders.values())
    saved = sum(_dec(o["calc"].get("saved")) or Decimal(0) for o in orders.values())
    return {
        "ok": True,
        "count": len(orders),
        "total_paid": str(total),
        "total_saved": str(saved),
        "ledger": str(path),
        "recovered_from": ledger.get("_recovered_from"),
    }


# ---------------- CLI ----------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="maimen-receipts ledger")
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER), help="ledger.json path")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_in = sub.add_parser("ingest", help="ingest order JSON file(s)")
    p_in.add_argument("files", nargs="+")
    sub.add_parser("stats", help="ledger stats")
    p_in2 = sub.add_parser("get", help="get one order")
    p_in2.add_argument("order_id")

    a = ap.parse_args(argv)
    path = Path(a.ledger)

    if a.cmd == "ingest":
        out = []
        for f in a.files:
            raw = json.loads(Path(f).read_text(encoding="utf-8"))
            out.append(ingest(path, raw))
        print(json.dumps({"ok": True, "results": out}, ensure_ascii=False, indent=2))
        return 0
    if a.cmd == "stats":
        print(json.dumps(stats(path), ensure_ascii=False, indent=2))
        return 0
    if a.cmd == "get":
        ledger = load(path)
        o = ledger.get("orders", {}).get(a.order_id)
        if o is None:
            print(json.dumps({"ok": False, "error": "order not found"}))
            return 1
        print(json.dumps({"ok": True, "order": o}, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
