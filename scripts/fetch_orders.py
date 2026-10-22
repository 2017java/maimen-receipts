"""fetch_orders — 用真实 MCP Token 拉历史订单 + 详情，喂给 ledger。

读 token 从环境变量 MCD_MCP_TOKEN 或 ~/.mcd-test/token.txt（后者仅本地调试用，
不要把 token 写进任何会被 commit 的文件）。

用法：
  export MCD_MCP_TOKEN=<token>   # 或使用 ~/.mcd-test/token.txt（仅本机）
  python scripts/fetch_orders.py --ledger ~/.maimen-receipts/ledger.json

产出：
  - 账本：~/.maimen-receipts/ledger.json
  - 原始快照：docs/real/raw_orders.json（脱敏）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skill" / "core"))
from ledger import DEFAULT_LEDGER, ingest  # noqa: E402

MCP_URL = "https://mcp.mcd.cn"
SENSITIVE_IN_RAW = {"storeAddress", "pickupCode", "payId", "expirePayTime"}


def load_token() -> str:
    tok = os.environ.get("MCD_MCP_TOKEN", "").strip()
    if tok:
        return tok
    fallback = Path.home() / ".mcd-test" / "token.txt"
    if fallback.exists():
        tok = fallback.read_text(encoding="utf-8-sig").strip()
        if tok.lower().startswith("bearer "):
            tok = tok[7:].strip()
        return tok
    raise SystemExit("no token: set MCD_MCP_TOKEN or create ~/.mcd-test/token.txt")


class MCPClient:
    def __init__(self, token: str):
        self.headers = {
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self.session_id: str | None = None
        self._ident = 0

    def rpc(self, method: str, params: dict | None = None, *, notify: bool = False):
        self._ident += 1
        payload = {"jsonrpc": "2.0", "method": method}
        if not notify:
            payload["id"] = self._ident
        if params is not None:
            payload["params"] = params
        h = dict(self.headers)
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(MCP_URL, data=json.dumps(payload).encode("utf-8"), headers=h)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                sid = r.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                    self.headers["Mcp-Session-Id"] = sid
                raw = r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            return {"transport_error": e.code, "body": body}
        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except ValueError:
            for block in raw.split("\n\n"):
                lines = [x[5:].strip() for x in block.splitlines() if x.startswith("data:")]
                if lines:
                    try:
                        obj = json.loads("\n".join(lines))
                        if obj.get("id") == self._ident:
                            return obj
                    except ValueError:
                        pass
            return {"parse_error": True, "raw_head": raw[:200]}

    def init(self):
        r = self.rpc("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "maimen-receipts", "version": "1.0"},
        })
        proto = r.get("result", {}).get("protocolVersion", "2025-03-26")
        self.headers["MCP-Protocol-Version"] = proto
        self.rpc("notifications/initialized", notify=True)
        return r

    def call(self, name: str, args: dict | None = None):
        return self.rpc("tools/call", {"name": name, "arguments": args or {}})


def unpack(resp: dict):
    result = resp.get("result", resp)
    if not isinstance(result, dict):
        return result
    if "structuredContent" in result:
        return result["structuredContent"]
    if "content" in result:
        parsed = []
        for b in result["content"]:
            if b.get("type") == "text":
                try:
                    parsed.append(json.loads(b["text"]))
                except ValueError:
                    parsed.append({"unparsed_text": b["text"][:500]})
        return parsed[0] if len(parsed) == 1 else parsed
    return result


def redact(obj):
    if isinstance(obj, dict):
        return {k: ("***REDACTED***" if k in SENSITIVE_IN_RAW else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    ap.add_argument("--save-raw", default=str(REPO_ROOT / "docs" / "real" / "raw_orders.json"))
    ap.add_argument("--max-detail", type=int, default=20, help="max query-order calls")
    a = ap.parse_args(argv)

    token = load_token()
    cli = MCPClient(token)
    init_resp = cli.init()
    if "result" not in init_resp:
        print(json.dumps({"ok": False, "stage": "initialize", "error": init_resp}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "stage": "initialize",
                      "server": init_resp["result"].get("serverInfo")},
                     ensure_ascii=False), flush=True)

    ol = unpack(cli.call("order-list"))
    if not isinstance(ol, dict):
        print(json.dumps({"ok": False, "stage": "order-list", "error": ol}, ensure_ascii=False))
        return 1
    orders = ol.get("data", {}).get("list", []) or []
    print(json.dumps({
        "ok": True, "stage": "order-list",
        "count": len(orders),
        "ids": [o.get("orderId") for o in orders],
    }, ensure_ascii=False), flush=True)

    raw_snapshots = [{"tool": "order-list", "data": redact(ol)}]
    detailed = 0
    results = []
    for o in orders[: a.max_detail]:
        oid = o.get("orderId")
        if not oid:
            continue
        detail = unpack(cli.call("query-order", {"orderId": oid}))
        raw_snapshots.append({"tool": "query-order", "orderId": oid, "data": redact(detail)})
        if not isinstance(detail, dict) or "data" not in detail:
            results.append({"orderId": oid, "ok": False, "error": "bad detail"})
            continue
        detailed += 1
        r = ingest(Path(a.ledger), {"data": detail["data"], "source": "mcp:query-order"})
        results.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)

    Path(a.save_raw).parent.mkdir(parents=True, exist_ok=True)
    Path(a.save_raw).write_text(
        json.dumps({"fetched_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                    "orders_list_count": len(orders),
                    "detailed_count": detailed,
                    "snapshots": raw_snapshots},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "ok": True,
        "stage": "done",
        "orders_list": len(orders),
        "detailed": detailed,
        "ledger": a.ledger,
        "raw_snapshot": a.save_raw,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
