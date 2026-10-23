"""export — 票根 / 票根册 HTML 渲染（热敏小票 × 集章 纸感令牌）。

视觉令牌（唯一真源 = maimengren DESIGN.md §2）：
  paper #F4F3EE / paper-raised #FBFAF7 / ink #1C1B18 / ink-60 #6E6C64
  stamp #C23A22 / mustard #E3A42B / savings #2E7D4F / receipt-line #E4E2DA

纪律：
  - 自绘，不碰官方 Logo / 菜品摄影图
  - 脱敏：默认不渲染订单号 / 手机号 / 地址 / 取餐码 / 支付号
  - 每张票根必须含"这一单相对原价省了 ¥X"或明确写"无法核价"
  - 每个营养数字旁标档位
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger import DEFAULT_LEDGER, _derive_calc, load  # noqa: E402
from pricing import audit_order  # noqa: E402
from nutrition import compute as compute_nutrition  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

TOKENS_CSS = """
:root{
  --paper:#F4F3EE; --paper-raised:#FBFAF7;
  --ink:#1C1B18; --ink-60:#6E6C64; --ink-30:#B4B1A6;
  --stamp:#C23A22; --mustard:#E3A42B; --savings:#2E7D4F;
  --receipt-line:#E4E2DA;
}
*{box-sizing:border-box;}
body{
  margin:0; padding:32px 16px; background:var(--paper); color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Segoe UI",sans-serif;
  font-size:14px; line-height:1.6;
}
.wrap{max-width:720px; margin:0 auto;}
.receipt{
  background:var(--paper-raised); border:1px solid var(--receipt-line);
  border-radius:2px; padding:24px 20px; margin:16px 0;
  box-shadow:0 1px 0 rgba(28,27,24,.04);
  position:relative;
}
.receipt::after{
  content:""; position:absolute; left:0; right:0; bottom:-8px; height:8px;
  background:repeating-linear-gradient(135deg, var(--paper-raised) 0 6px, transparent 6px 12px);
}
.receipt-header{
  border-bottom:1px dashed var(--receipt-line); padding-bottom:12px; margin-bottom:12px;
}
.brand{font-size:12px; letter-spacing:.24em; color:var(--ink-60); text-transform:uppercase;}
.receipt-title{font-size:22px; font-weight:700; margin:6px 0 2px;}
.receipt-meta{color:var(--ink-60); font-size:12px;}
.mono{font-family:"JetBrains Mono","SF Mono",Consolas,monospace; font-variant-numeric:tabular-nums;}
.row{display:flex; justify-content:space-between; gap:12px; padding:3px 0;}
.row .name{flex:1;}
.row .num{white-space:nowrap;}
.sep{border-top:1px dashed var(--receipt-line); margin:12px 0;}
.saved-line{
  background:rgba(46,125,79,.10); color:var(--savings);
  padding:8px 12px; border-left:3px solid var(--savings); margin:12px 0;
  font-weight:600;
}
.unavailable{
  background:rgba(227,164,43,.12); color:#8A5D00;
  padding:8px 12px; border-left:3px solid var(--mustard); margin:12px 0;
}
.stamp{
  display:inline-block; border:2px solid var(--stamp); color:var(--stamp);
  padding:2px 10px; border-radius:999px; font-size:11px; letter-spacing:.12em;
  transform:rotate(-6deg); text-transform:uppercase;
}
.stamp.est{border-color:var(--mustard); color:#8A5D00;}
.stamp.miss{border-color:var(--ink-30); color:var(--ink-60);}
.note{
  background:rgba(227,164,43,.12); border-left:3px solid var(--mustard);
  padding:8px 12px; margin:12px 0; color:var(--ink);
}
.privacy{color:var(--ink-30); font-size:11px; margin-top:16px;}
.foot{color:var(--ink-60); font-size:11px; margin-top:24px; text-align:center;}
h2.section{
  font-size:12px; letter-spacing:.18em; color:var(--ink-60);
  text-transform:uppercase; margin:24px 0 8px;
}
.demo-banner{
  background:rgba(194,58,34,.08); color:var(--stamp);
  border-bottom:1px solid rgba(194,58,34,.22);
  text-align:center; padding:8px; font-size:11px; letter-spacing:.18em;
  font-weight:600;
}
.detail{
  margin:8px 0 4px; border-top:1px solid var(--receipt-line); padding-top:6px;
}
.detail-row{
  display:flex; gap:8px; align-items:baseline;
  font-size:12px; padding:2px 0; color:var(--ink-60);
}
.detail-row .d-name{flex:1; color:var(--ink);}
.detail-row .d-tier{
  font-size:10px; letter-spacing:.06em; white-space:nowrap;
  color:var(--ink-60);
}
.detail-row .d-num{white-space:nowrap; min-width:72px; text-align:right;}
.detail-row.missing .d-name{color:var(--ink-60);}
.detail-row.missing .d-tier{color:var(--stamp);}
.detail-row.missing .d-num{color:var(--ink-30);}
.month-card{
  background:var(--paper-raised); border:1px solid var(--receipt-line);
  padding:16px; margin:16px 0; border-radius:2px;
}
.stat-grid{display:grid; grid-template-columns:repeat(3,1fr); gap:12px;}
.stat{background:var(--paper); padding:12px; border:1px solid var(--receipt-line); border-radius:2px;}
.stat .label{font-size:11px; color:var(--ink-60); letter-spacing:.12em;}
.stat .value{font-size:22px; font-weight:700; color:var(--ink); margin-top:4px;}
.stat .value.savings{color:var(--savings);}
"""


def _esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def _tier_stamp(tier: str) -> str:
    """按总档位出角标：精确=实测 / 含规格映射=实测·规格映射 / 其他=估算 / 未收录。"""
    if not tier:
        return '<span class="stamp miss">官方未收录</span>'
    if "精确" in tier:
        return '<span class="stamp">实测</span>'
    if "规格映射" in tier or "含规格" in tier:
        return '<span class="stamp">实测·规格映射</span>'
    if "估算" in tier or "estimat" in tier.lower():
        return '<span class="stamp est">估算±20%</span>'
    return '<span class="stamp miss">官方未收录</span>'


def render_receipt(order: dict, *, demo: bool = False, embedded: bool = False) -> str:
    o = order["official"]
    calc = order.get("calc", {}) or audit_order(o)
    personal = order.get("personal", {}) or {}
    items = o.get("items", [])

    # 计算营养（若未缓存）
    nut = order.get("calc", {}).get("nutrition_full")
    if not nut:
        nut = compute_nutrition(items)

    lines = []
    lines.append(f'<div class="receipt-title mono">{_esc(o.get("storeName", "麦当劳"))}</div>')
    lines.append(f'<div class="receipt-meta mono">{_esc(o.get("createTime", ""))}</div>')

    lines.append('<div class="sep"></div>')
    for it in items:
        price = it.get("price", "")
        price_s = f'¥{_esc(price)}' if price else '—'
        lines.append(
            f'<div class="row"><span class="name">{_esc(it.get("name",""))} ×{_esc(it.get("qty",1))}</span>'
            f'<span class="num mono">{price_s}</span></div>'
        )
        for c in it.get("combo", []) or []:
            lines.append(
                f'<div class="row" style="padding-left:16px;color:var(--ink-60);font-size:12px;">'
                f'<span class="name">└ {_esc(c.get("name",""))} ×{_esc(c.get("qty",1))}</span>'
                f'<span class="num mono"></span></div>'
            )

    # 金额
    lines.append('<div class="sep"></div>')
    total = o.get("totalAmount") or calc.get("total")
    real = o.get("realTotalAmount") or calc.get("real")
    if total:
        lines.append(f'<div class="row"><span class="name">原价合计</span><span class="num mono">¥{_esc(total)}</span></div>')
    if real:
        lines.append(f'<div class="row"><span class="name">实付</span><span class="num mono">¥{_esc(real)}</span></div>')

    # 省下（口径纪律：不写"帮你省了"）
    saved = calc.get("saved")
    if saved is not None:
        pct = calc.get("saved_pct")
        pct_s = f"（省 {pct}%）" if pct else ""
        lines.append(
            f'<div class="saved-line">这一单相对原价省了 ¥{_esc(saved)}{pct_s}</div>'
        )
    else:
        reason = calc.get("reason", "原价数据不足")
        lines.append(
            f'<div class="unavailable">无法核价（{_esc(reason)}）— 不编造，如需请核对 query-meals 菜单价</div>'
        )

    # 营养
    lines.append('<h2 class="section">Nutrition · 营养</h2>')
    totals = nut.get("totals", {})
    lines.append(
        f'<div class="row"><span class="name">能量 {_tier_stamp(nut.get("tier",""))}</span>'
        f'<span class="num mono">{_esc(totals.get("energy_kj", 0))} kJ</span></div>'
    )
    lines.append(
        f'<div class="row"><span class="name">蛋白 / 脂肪 / 碳水</span>'
        f'<span class="num mono">{_esc(totals.get("protein_g",0))} / {_esc(totals.get("fat_g",0))} / {_esc(totals.get("carb_g",0))} g</span></div>'
    )
    lines.append(
        f'<div class="row"><span class="name">钠</span>'
        f'<span class="num mono">{_esc(totals.get("sodium_mg", 0))} mg</span></div>'
    )
    lines.append(f'<div class="privacy">数据覆盖：{_esc(nut.get("disclosure",""))}（钠不反推，缺即缺）</div>')

    # 逐项营养明细（让"未收录"看得见，而不是只给一个 N/M）
    rows = nut.get("rows", [])
    if rows:
        detail = []
        for r in rows:
            name = _esc(r.get("name", ""))
            qty = _esc(r.get("qty", 1))
            tier_label = r.get("tier", "")
            e = r.get("energy_kj")
            if e is not None:
                detail.append(
                    f'<div class="detail-row"><span class="d-name">{name} ×{qty}</span>'
                    f'<span class="d-tier">{_esc(tier_label)}</span>'
                    f'<span class="d-num mono">{_esc(round(e, 1))} kJ</span></div>'
                )
            else:
                detail.append(
                    f'<div class="detail-row missing"><span class="d-name">{name} ×{qty}</span>'
                    f'<span class="d-tier">{_esc(tier_label)}</span>'
                    f'<span class="d-num mono">—</span></div>'
                )
        lines.append('<div class="detail">' + "".join(detail) + '</div>')

    if nut.get("rejected_rows"):
        names = ", ".join(_esc(r.get("name","")) for r in nut["rejected_rows"])
        lines.append(f'<div class="privacy">已剔除矛盾/占位行：{names}</div>')

    # 备注
    if personal.get("note"):
        lines.append('<h2 class="section">Note · 一句话记忆</h2>')
        lines.append(f'<div class="note">「{_esc(personal["note"])}」</div>')

    # 脱敏
    masked = order.get("privacy", {}).get("orderId_masked", "****")
    lines.append(f'<div class="privacy mono">票号 {_esc(masked)}（订单号 / 手机号 / 地址 / 取餐码 / 支付号 默认不渲染）</div>')

    banner = '<div class="demo-banner">演示数据 · DEMO</div>' if (demo and not embedded) else ''

    body = f"""<div class="receipt">
  <div class="receipt-header">
    <div class="brand">maimen · receipts</div>
    {''.join(lines)}
  </div>
</div>"""

    if embedded:
        return body

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>麦门票根 · {_esc(o.get("createTime",""))}</title>
<style>{TOKENS_CSS}</style></head>
<body>{banner}<div class="wrap">
{body}
<div class="foot">由 maimen-receipts 生成 · 输出非医疗或营养专业建议</div>
</div></body></html>"""


def render_book(ledger: dict, month: str, *, demo: bool = False) -> str:
    """月度小结 + 票根流 + 检索入口。month=YYYY-MM。"""
    orders = ledger.get("orders", {})
    in_month = {
        oid: o for oid, o in orders.items()
        if o.get("official", {}).get("createTime", "").startswith(month)
    }
    count = len(in_month)
    paid = sum(float(o["official"].get("realTotalAmount") or 0) for o in in_month.values())
    saved = sum(float(o.get("calc", {}).get("saved") or 0) for o in in_month.values())

    # 营养 TOP（按能量）
    top = []
    for oid, o in in_month.items():
        nut = o.get("calc", {}).get("nutrition_full")
        if not nut:
            nut = compute_nutrition(o.get("official", {}).get("items", []))
        top.append((oid, o, nut))
    top.sort(key=lambda x: -(x[2].get("totals", {}).get("energy_kj", 0)))

    cards = []
    for oid, o, _ in top:
        cards.append(render_receipt(o, demo=demo, embedded=True))

    banner = '<div class="demo-banner">演示数据 · DEMO</div>' if demo else ''

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>麦门票根册 · {_esc(month)}</title>
<style>{TOKENS_CSS}</style></head>
<body>{banner}<div class="wrap">
<h1 style="letter-spacing:.18em; font-size:14px; color:var(--ink-60);">MAIMEN · RECEIPTS · {_esc(month)}</h1>
<div class="month-card">
  <div class="stat-grid">
    <div class="stat"><div class="label">ORDERS · 单数</div><div class="value mono">{count}</div></div>
    <div class="stat"><div class="label">PAID · 支出</div><div class="value mono">¥{paid:.2f}</div></div>
    <div class="stat"><div class="label">SAVED · 省下</div><div class="value mono savings">¥{saved:.2f}</div></div>
  </div>
</div>
<h2 class="section">Receipts · 票根流</h2>
{''.join(cards)}
<div class="foot">由 maimen-receipts 生成 · 数据口径见 references/data-integrity.md · 输出非医疗或营养专业建议</div>
</div></body></html>"""


# ---------------- CLI ----------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="maimen-receipts export")
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    ap.add_argument("-o", "--out", default="docs/outputs")
    ap.add_argument("--demo", action="store_true", help="mark output as demo data")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_r = sub.add_parser("receipt")
    p_r.add_argument("order_id")

    p_b = sub.add_parser("book")
    p_b.add_argument("month", help="YYYY-MM")

    a = ap.parse_args(argv)
    path = Path(a.ledger)
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = load(path)

    if a.cmd == "receipt":
        o = ledger.get("orders", {}).get(a.order_id)
        if o is None:
            print(json.dumps({"ok": False, "error": "order not found"}))
            return 1
        if not o.get("calc", {}).get("nutrition_full"):
            o["calc"] = _derive_calc(o["official"])
        html_s = render_receipt(o, demo=a.demo)
        fp = out_dir / f"receipt-{a.order_id}.html"
        fp.write_text(html_s, encoding="utf-8")
        print(json.dumps({"ok": True, "file": str(fp), "order_id": a.order_id}, ensure_ascii=False))
        return 0

    if a.cmd == "book":
        for o in ledger.get("orders", {}).values():
            if not o.get("calc", {}).get("nutrition_full"):
                o["calc"] = _derive_calc(o["official"])
        html_s = render_book(ledger, a.month, demo=a.demo)
        fp = out_dir / f"book-{a.month}.html"
        fp.write_text(html_s, encoding="utf-8")
        print(json.dumps({"ok": True, "file": str(fp), "month": a.month}, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
