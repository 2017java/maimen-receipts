"""nutrition — 营养三档计算 + 异常行剔除 + 覆盖度标注。

单一真源：references/algorithms.md §二。
纪律：
  - 钠永不反推
  - 套餐父子不双算
  - 缺数据标 `官方未收录`，不编造
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "nutrition_official.json"

# 14 列下标 -> 字段（已核验部分）
COLS = {
    0: "weight_g",
    1: "energy_kj",
    2: "protein_g",
    3: "fat_g",
    4: "carb_g",
    5: "sodium_mg",
    10: "cholesterol_mg",  # 推断
    11: "sugar_g",         # 推断
    13: "calcium_mg",
}
REPORT_COLS = ["energy_kj", "protein_g", "fat_g", "carb_g", "sodium_mg"]

_FULLWIDTH = "（）：／　"
_HALFWIDTH = "():/ "


def _norm(s: str) -> str:
    """全角/半角括号等归一。"""
    if not s:
        return ""
    for i, c in enumerate(_FULLWIDTH):
        s = s.replace(c, _HALFWIDTH[i])
    s = s.replace("　", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _load_table(path: Path = DATA_PATH) -> dict[str, dict]:
    """展开为 {归一化名称(含规格): nutrient dict}。"""
    obj = json.loads(path.read_text(encoding="utf-8"))
    raw = obj["data"] if "data" in obj else obj
    products: dict = raw["Product"]
    specs: dict = raw["ProductType"]

    table: dict[str, dict] = {}
    for pid, p in products.items():
        pname = p.get("title", "")
        for tid in p.get("ProductType", []):
            t = specs.get(tid)
            if not t:
                continue
            spec_title = t.get("title", "")
            nutri = t.get("nutrition") or []
            rec = {}
            for idx, key in COLS.items():
                if idx < len(nutri):
                    try:
                        rec[key] = float(nutri[idx])
                    except (TypeError, ValueError):
                        rec[key] = None
            # 键名：单品名 + 规格（规格非"默认/1个"时）
            key = _norm(pname)
            if spec_title and spec_title not in ("默认", "1个"):
                key = _norm(f"{pname}{spec_title}")
            table[key] = {"name": pname, "spec": spec_title, **rec}
            # 同时登记纯名（避免歧义时不覆盖已有多规格键）
            base = _norm(pname)
            if base not in table:
                table[base] = table[key]
    return table


def _is_contradictory(rec: dict) -> bool:
    """物理矛盾 / 占位行。"""
    kcal = rec.get("energy_kj")
    carb = rec.get("carb_g")
    if kcal is not None and carb is not None and kcal <= 0 and carb > 0.5:
        return True
    vals = [rec.get(k) for k in REPORT_COLS]
    if all(v == 0 for v in vals):
        return True
    return False


def _strip_customizations(name: str) -> str:
    """剥离点单定制后缀，得到品名主干。

    实测 MCP 订单 itemName 形如：
      '可乐中杯 冰(去冰)'  -> '可乐中杯'
      '板烧鸡腿堡 去生菜'  -> '板烧鸡腿堡'
      '薯条中 不要盐'      -> '薯条中'
    规则：以空白或 "（/(" 开始的片段（定制选项）整体切掉。
    """
    s = _norm(name)
    # 切掉以空白 + 任意（含括号）开头的尾巴
    for sep in [" ", "　"]:
        idx = s.find(sep)
        if idx > 0:
            s = s[:idx]
    # 切掉以全/半角左括号开始的尾巴
    for br in ["(", "（"]:
        idx = s.find(br)
        if idx > 0:
            s = s[:idx]
    return s.strip()


def _lookup(table: dict[str, dict], name: str) -> tuple[str, dict | None]:
    """查找策略（命中优先）：
    1. 精确同名
    2. 剥离定制后缀（"可乐中杯 冰(去冰)" -> "可乐中杯"）后精确
    3. 规格标记抽取：识别 "中/大/小/迷你" 与量词 "杯/块/份/个/盒/包"，去词缀后匹配 "名+规格" 或 "名"
    4. 含匹配：产品名片段互含（"可乐"⊂"可口可乐"）时挑最接近规格的记录
    5. 全部失败 -> missing（标 "官方未收录"，不编造）
    """
    raw = _norm(name)
    # 先试原名；再试去定制后缀
    candidates_names = [raw]
    stripped_custom = _strip_customizations(name)
    if stripped_custom != raw:
        candidates_names.append(stripped_custom)

    for key in candidates_names:
        if key in table:
            return "exact", table[key]

    key = candidates_names[-1]  # 用去定制后的主干做后续模糊匹配

    size_tokens = ["迷你", "大杯", "中杯", "小杯", "大", "中", "小"]
    unit_tokens = ["杯", "块", "份", "个", "盒", "包"]

    # 剥离量词（在末尾）
    stripped = key
    for u in unit_tokens:
        if stripped.endswith(u) and len(stripped) > len(u):
            stripped = stripped[: -len(u)]
            break

    # 尝试候选
    cands: list[str] = []
    # 情况 A：前缀规格 "中薯条" -> base=薯条
    for s in size_tokens:
        if stripped.startswith(s) and len(stripped) > len(s):
            base = stripped[len(s):]
            cands.extend([base + s, base])
    # 情况 B：后缀规格 "薯条中" / "可口可乐中" / "可乐中杯" -> 剥离量词得 "可乐中"，含匹配
    for s in size_tokens:
        if stripped.endswith(s) and len(stripped) > len(s):
            base = stripped[: -len(s)]
            cands.extend([base + s, base])
    # 情况 C：无规格 -> 仅 base
    cands.append(stripped)
    cands.append(key)

    for c in cands:
        if c in table:
            return "spec-mapped", table[c]

    # 含匹配：取产品名片段互含的记录
    matches = [(k, rec) for k, rec in table.items()
               if key in k or k in key or stripped in k or k in stripped]
    if matches:
        # 优先带同规格标记的
        for s in size_tokens:
            for k, rec in matches:
                if k.endswith(s):
                    return "spec-mapped", rec
        return "spec-mapped", matches[0][1]

    return "missing", None


def _estimate_from_macros(rec: dict) -> dict | None:
    """4-4-9 反推能量（同主料换酱场景）。返回估算营养或 None。"""
    p = rec.get("protein_g")
    c = rec.get("carb_g")
    f = rec.get("fat_g")
    if p is None or c is None or f is None:
        return None
    kcal = p * 4 + c * 4 + f * 9
    return {
        "energy_kj": round(kcal * 4.184, 1),
        "protein_g": p,
        "fat_g": f,
        "carb_g": c,
        "sodium_mg": None,  # 钠永不反推
    }


def compute(order_items: list[dict], table: dict | None = None) -> dict:
    """order_items: 接受 MCP 原始字段（productName/quantity/comboItemList[{itemName,itemQuantity}]）
    或归一化字段（name/qty/combo[{name,qty}]）。
    套餐父子不双算：有 combo 的父项跳过，只累加子项。
    """
    if table is None:
        table = _load_table()

    def _it_name(it: dict) -> str:
        return it.get("name") or it.get("productName") or ""

    def _it_qty(it: dict) -> int:
        try:
            return int(it.get("qty") or it.get("quantity") or 1)
        except (TypeError, ValueError):
            return 1

    def _it_combo(it: dict) -> list[dict]:
        raw = it.get("combo") or it.get("comboItemList") or []
        out = []
        for c in raw:
            out.append({
                "name": c.get("name") or c.get("itemName") or "",
                "qty": int(c.get("qty") or c.get("itemQuantity") or 1),
            })
        return out

    flat: list[dict] = []
    for it in order_items:
        qty = _it_qty(it)
        combo = _it_combo(it)
        if combo:
            for c in combo:
                cqty = int(c["qty"]) * qty
                flat.append({"name": c["name"], "qty": cqty, "from_combo": True})
        else:
            flat.append({"name": _it_name(it), "qty": qty, "from_combo": False})

    total = len(flat)
    rejected: list[dict] = []
    matched = 0
    exact = 0
    estimated = 0
    missing = 0
    agg = {k: Decimal(0) for k in REPORT_COLS}
    rows: list[dict] = []

    for f in flat:
        tier, rec = _lookup(table, f["name"])
        if rec is None:
            missing += 1
            rows.append({"name": f["name"], "qty": f["qty"], "tier": "官方未收录"})
            continue
        if _is_contradictory(rec):
            rejected.append({"name": f["name"], "reason": "contradictory/placeholder row", "raw": rec})
            rows.append({"name": f["name"], "qty": f["qty"], "tier": "剔除", "reason": "矛盾/占位行"})
            continue

        # 用真实官方值（精确或规格映射都可靠）；仅在官方值缺字段时才 4-4-9 反推
        use = {k: rec.get(k) for k in REPORT_COLS}
        if any(use.get(k) is None for k in ["energy_kj", "protein_g", "fat_g", "carb_g"]):
            est = _estimate_from_macros(rec)
            if est is not None:
                use.update(est)
        if tier == "exact":
            t_label = "精确"
            exact += 1
        else:  # spec-mapped
            t_label = "规格映射"
            estimated += 1
        matched += 1

        q = Decimal(f["qty"])
        for k in REPORT_COLS:
            v = use.get(k)
            if v is not None:
                agg[k] += Decimal(str(v)) * q
        rows.append({
            "name": f["name"], "qty": f["qty"],
            "tier": t_label,
            "energy_kj": use.get("energy_kj"),
            "protein_g": use.get("protein_g"),
            "fat_g": use.get("fat_g"),
            "carb_g": use.get("carb_g"),
            "sodium_mg": use.get("sodium_mg"),
        })

    # 总档位
    if exact == matched and matched > 0:
        overall = "精确"
    elif matched > 0:
        overall = "含规格映射"
    else:
        overall = "官方未收录"

    return {
        "tier": overall,
        "matched_items": matched,
        "total_items": total,
        "exact": exact,
        "estimated": estimated,  # 规格映射（可靠，非估算）
        "missing": missing,
        "totals": {k: float(agg[k]) if agg[k] else 0.0 for k in REPORT_COLS},
        "rejected_rows": rejected,
        "rows": rows,
        "coverage_pct": round(matched / total * 100, 1) if total else 0.0,
        "disclosure": f"已匹配 {matched}/{total} 项",
    }
