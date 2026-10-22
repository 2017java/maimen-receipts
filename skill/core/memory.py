"""memory — 个人记忆层：补一句话 / 一句话找回。

纪律：
  - 只改 personal 层，不动 official 交易事实
  - 检索无命中 -> 返回「没找到」，不猜经历
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger import DEFAULT_LEDGER, load, save  # noqa: E402


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", " ", s).strip().lower()


def note(path: Path, order_id: str, text: str, tags: list[str] | None = None) -> dict:
    ledger = load(path)
    entry = ledger.get("orders", {}).get(order_id)
    if entry is None:
        return {"ok": False, "error": "order not found", "order_id": order_id}
    entry.setdefault("personal", {"note": "", "tags": [], "would_reorder": None})
    entry["personal"]["note"] = text
    if tags:
        entry["personal"]["tags"] = tags
    save(path, ledger)
    return {"ok": True, "order_id": order_id, "note": text, "ledger": str(path)}


def _parse_date_query(q: str) -> tuple[str | None, str | None]:
    """识别日期意图 -> (start_iso, end_iso) 或 (None, None)。"""
    qn = _norm(q)
    today = datetime.now().date()
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", qn)
    if m:
        d = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return d, d
    m = re.search(r"(20\d{2})-(\d{2})", qn)
    if m:
        return f"{m.group(1)}-{m.group(2)}-01", f"{m.group(1)}-{m.group(2)}-31"
    if "本月" in qn or "这个月" in qn:
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat()
    if "上周" in qn:
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start.isoformat(), end.isoformat()
    return None, None


def search(path: Path, query: str, limit: int = 20) -> dict:
    ledger = load(path)
    orders = ledger.get("orders", {})
    q = _norm(query)
    d_start, d_end = _parse_date_query(query)

    hits = []
    for oid, o in orders.items():
        official = o.get("official", {})
        personal = o.get("personal", {})
        note_text = personal.get("note", "")
        tags = personal.get("tags", [])
        create = official.get("createTime", "")[:10]

        score = 0
        why = []
        if q and q in _norm(note_text):
            score += 3
            why.append("note")
        if q and any(q in _norm(t) for t in tags):
            score += 2
            why.append("tag")
        if q and q in _norm(official.get("storeName", "")):
            score += 1
            why.append("store")
        if q and any(q in _norm(it.get("name", "")) for it in official.get("items", [])):
            score += 1
            why.append("item")
        if d_start and d_end and d_start <= create <= d_end:
            score += 2
            why.append("date")

        if score > 0:
            hits.append({
                "order_id": oid,
                "date": create,
                "store": official.get("storeName", ""),
                "paid": official.get("realTotalAmount", ""),
                "saved": o.get("calc", {}).get("saved"),
                "note": note_text,
                "score": score,
                "matched": why,
            })

    hits.sort(key=lambda x: (-x["score"], x["date"]), reverse=False)
    hits = hits[:limit]
    return {
        "ok": True,
        "query": query,
        "count": len(hits),
        "hits": hits,
        "message": "" if hits else "没找到",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="maimen-receipts memory")
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_n = sub.add_parser("note")
    p_n.add_argument("order_id")
    p_n.add_argument("text")
    p_n.add_argument("--tags", nargs="*", default=None)

    p_s = sub.add_parser("search")
    p_s.add_argument("query")
    p_s.add_argument("--limit", type=int, default=20)

    a = ap.parse_args(argv)
    path = Path(a.ledger)

    if a.cmd == "note":
        print(json.dumps(note(path, a.order_id, a.text, a.tags), ensure_ascii=False, indent=2))
        return 0
    if a.cmd == "search":
        print(json.dumps(search(path, a.query, a.limit), ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
