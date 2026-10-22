"""pricing — 省钱核价（三场景）。

口径纪律（不可破）：
  - 只写「这一单相对原价省了 ¥X」
  - 原价来源只信 totalAmount / query-meals 菜单价
  - 一律不信 calculate-price.originalPrice（实测虚高）

单一真源：references/algorithms.md §一。
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _dec(s: Any) -> Decimal | None:
    if s is None:
        return None
    try:
        return Decimal(str(s).strip())
    except (InvalidOperation, ValueError):
        return None


def audit_order(official: dict) -> dict:
    """历史订单核价（主场景）。精确。

    依赖 query-order 自洽性：totalAmount - totalDiscountAmount = realTotalAmount
    （实测已验证）。返回 saved / saved_pct / 口径说明。
    """
    total = _dec(official.get("totalAmount"))
    real = _dec(official.get("realTotalAmount"))
    disc = _dec(official.get("totalDiscountAmount"))

    if real is None:
        return {"tier": "unavailable", "reason": "missing realTotalAmount", "saved": None}
    if total is None and disc is not None:
        total = real + disc
    if total is None:
        return {"tier": "unavailable", "reason": "missing totalAmount", "saved": None}

    saved = total - real
    if saved < 0:
        # 数据异常：实付大于原价 -> 不编造，如实报告
        return {
            "tier": "anomaly",
            "reason": "realTotalAmount > totalAmount",
            "total": str(total),
            "real": str(real),
            "saved": None,
        }

    pct = (saved / total * 100) if total > 0 else Decimal(0)
    return {
        "tier": "exact",
        "method": "totalAmount - realTotalAmount (from query-order)",
        "total": str(total),
        "real": str(real),
        "discount": str(disc) if disc is not None else None,
        "saved": str(saved),
        "saved_pct": f"{pct:.1f}",
        "wording": f"这一单相对原价省了 ¥{saved:.2f}",
    }


def compare_menu(items: list[dict], menu_price_by_name: dict[str, Decimal]) -> dict:
    """单品当前价对比（可靠）。

    items: [{name, qty, price}]  (price=订单实付单价, 可为空)
    menu_price_by_name: {商品名: 菜单价 Decimal}
    逐项比：菜单价×qty  vs  订单实付单价×qty
    """
    rows, matched, total = [], 0, len(items)
    menu_sum = Decimal(0)
    paid_sum = Decimal(0)
    for it in items:
        name = it.get("name", "")
        qty = Decimal(it.get("qty") or 1)
        mp = menu_price_by_name.get(name)
        paid = _dec(it.get("price"))
        if mp is None:
            rows.append({"name": name, "qty": str(qty), "tier": "menu-missing"})
            continue
        matched += 1
        m_total = mp * qty
        p_total = (paid * qty) if paid is not None else None
        menu_sum += m_total
        if p_total is not None:
            paid_sum += p_total
        rows.append({
            "name": name, "qty": str(qty),
            "menu_price": str(mp), "menu_total": str(m_total),
            "paid_price": str(paid) if paid is not None else None,
            "tier": "exact",
        })
    saved = menu_sum - paid_sum if paid_sum > 0 else None
    return {
        "tier": "exact" if matched == total else "partial",
        "matched_items": matched,
        "total_items": total,
        "menu_sum": str(menu_sum),
        "paid_sum": str(paid_sum) if paid_sum > 0 else None,
        "saved": str(saved) if saved is not None else None,
        "rows": rows,
    }


def estimate_with_calculate_price(calculate_price_resp: dict, menu_cross_check: dict | None = None) -> dict:
    """预估下单价（辅助）。永远标 ⚠️ 陷阱。

    不信任 calculate-price.originalPrice。若提供了 menu_cross_check，
    以菜单价为准并标 verify=menu。
    """
    data = calculate_price_resp.get("data", calculate_price_resp)
    raw_original = _dec(data.get("originalPrice"))
    real = _dec(data.get("realPrice") or data.get("payFee") or data.get("price"))
    out = {
        "tier": "estimated",
        "warning": "calculate-price.originalPrice 实测虚高，不作对账基准；只作估算参考",
        "original_price_raw": str(raw_original) if raw_original is not None else None,
        "estimated_real": str(real) if real is not None else None,
        "traps": [
            "roundList 参数不生效（传即 60006），套餐按主商品码整体算",
            "历史订单重算会报 60006（商品下架）",
            "originalPrice 虚高",
            "不配券时 discount=0，券优惠需 available-coupons 补充",
        ],
    }
    if menu_cross_check and menu_cross_check.get("menu_sum"):
        out["verify"] = "menu"
        out["menu_sum"] = menu_cross_check["menu_sum"]
        out["wording"] = f"参考菜单价 ¥{menu_cross_check['menu_sum']}（calculate-price 仅估算）"
    else:
        out["verify"] = "none"
    return out
