"""test_ledger — 验收用例（v6 §五）。

跑： python -m pytest skill/tests/ -q
或： python skill/tests/test_ledger.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent / "core"
sys.path.insert(0, str(CORE))

from ledger import ingest, load, save  # noqa: E402
from pricing import audit_order  # noqa: E402
from nutrition import compute as compute_nutrition, _is_contradictory  # noqa: E402
from memory import note as mem_note, search as mem_search  # noqa: E402


def _order(oid="A1", total="36.60", real="23.90", disc="12.70"):
    return {
        "data": {
            "orderId": oid,
            "createTime": "2026-10-22 12:00:00",
            "storeName": "麦当劳·示例店",
            "orderStatus": "已完成",
            "totalAmount": total,
            "realTotalAmount": real,
            "totalDiscountAmount": disc,
            "orderProductList": [
                {
                    "productName": "大堡口福三件套",
                    "quantity": 1,
                    "price": "23.90",
                    "comboItemList": [
                        {"itemName": "麦辣鸡腿汉堡", "itemQuantity": 1},
                        {"itemName": "中薯条", "itemQuantity": 1},
                        {"itemName": "可乐中杯", "itemQuantity": 1},
                    ],
                }
            ],
        }
    }


def t1_dedup():
    """1) 同单导入两次 -> 账本仍一条。"""
    p = Path(tempfile.mkdtemp()) / "ledger.json"
    r1 = ingest(p, _order("A1"))
    r2 = ingest(p, _order("A1"))
    l = load(p)
    assert r1["added"] == 1 and r2["deduped"] is True
    assert len(l["orders"]) == 1
    return "t1 ok"


def t2_pricing_wording():
    """5) 省钱口径为「这一单相对原价省了 X」，精确档。"""
    r = audit_order(_order()["data"])
    assert r["tier"] == "exact"
    assert r["saved"] == "12.70"
    assert r["wording"] == "这一单相对原价省了 ¥12.70"
    assert "帮你省" not in r["wording"]
    return "t2 ok"


def t3_pricing_anomaly():
    """2) 未填价不污染统计：实付 > 原价时标 anomaly，saved=None。"""
    r = audit_order(_order(total="10.00", real="23.90", disc="0")["data"])
    assert r["tier"] == "anomaly" and r["saved"] is None
    return "t3 ok"


def t4_combo_no_double_count():
    """3) 套餐父子不双算：有 combo 的父项跳过，只累加子项。"""
    n = compute_nutrition(_order()["data"]["orderProductList"])
    # 三件套 -> 3 个子项（不是 4：父+子）
    assert n["total_items"] == 3
    return "t4 ok"


def t5_contradictory_rejected():
    """3) 矛盾/占位行被剔除且留痕。"""
    # 无糖可乐中杯：kcal=0 但 carb=1
    rec = {"energy_kj": 0, "carb_g": 1.0, "protein_g": 0, "fat_g": 0, "sodium_mg": 35}
    assert _is_contradictory(rec) is True
    return "t5 ok"


def t6_nutrition_disclosure():
    """4) 营养匹配只算成功项，票根明示「已匹配 N/M」。"""
    n = compute_nutrition(_order()["data"]["orderProductList"])
    assert "已匹配" in n["disclosure"]
    assert n["matched_items"] + n["missing"] == n["total_items"]
    return "t6 ok"


def t7_personal_preserved():
    """7) 接口未返回旧单 -> 本地记录不删；个人层备注保留。"""
    p = Path(tempfile.mkdtemp()) / "ledger.json"
    ingest(p, _order("A1"))
    mem_note(p, "A1", "面试结束，奖励自己")
    # 重新导入 -> personal 保留
    ingest(p, _order("A1"))
    l = load(p)
    assert l["orders"]["A1"]["personal"]["note"] == "面试结束，奖励自己"
    return "t7 ok"


def t8_corrupt_backup():
    """8) 账本损坏 -> 先备份再空态，不静默清空。"""
    d = Path(tempfile.mkdtemp())
    p = d / "ledger.json"
    p.write_text("{not json", encoding="utf-8")
    l = load(p)
    assert l["orders"] == {}
    backups = list(d.glob("ledger.corrupt.*.json"))
    assert len(backups) == 1, "corrupt file must be backed up"
    return "t8 ok"


def t9_memory_search():
    """一句话找回；无命中 -> 「没找到」。"""
    p = Path(tempfile.mkdtemp()) / "ledger.json"
    ingest(p, _order("A1"))
    mem_note(p, "A1", "面试结束，奖励自己")
    hit = mem_search(p, "面试")
    assert hit["count"] >= 1 and hit["hits"][0]["order_id"] == "A1"
    miss = mem_search(p, "滑雪")
    assert miss["count"] == 0 and miss["message"] == "没找到"
    return "t9 ok"


def t10_privacy_stripped():
    """10) 脱敏：不存 storeAddress/pickupCode/payId。"""
    raw = _order("A1")
    raw["data"]["storeAddress"] = "某市某区某路 1 号"
    raw["data"]["pickupCode"] = "8888"
    raw["data"]["payId"] = "PAY-SECRET-123"
    p = Path(tempfile.mkdtemp()) / "ledger.json"
    ingest(p, raw)
    s = p.read_text(encoding="utf-8")
    assert "某市某区" not in s and "8888" not in s and "PAY-SECRET" not in s
    return "t10 ok"


def t11_multi_qty_not_same_minute():
    """1) 不同订单不因同分钟合并。"""
    p = Path(tempfile.mkdtemp()) / "ledger.json"
    a = _order("A1")
    b = _order("A2")
    b["data"]["createTime"] = a["data"]["createTime"]  # 同一分钟
    ingest(p, a); ingest(p, b)
    assert len(load(p)["orders"]) == 2
    return "t11 ok"


def t12_customization_suffix():
    """12) 定制后缀（"可乐中杯 冰(去冰)" / "薯条中 不要盐"）不影响营养匹配。"""
    from nutrition import _lookup, _strip_customizations, _load_table
    t = _load_table()
    for name, want_tier in [
        ("可乐中杯 冰(去冰)", "spec-mapped"),
        ("薯条中 不要盐", "exact"),
        ("板烧鸡腿堡 去生菜", "exact"),
    ]:
        tier, rec = _lookup(t, name)
        assert tier == want_tier, f"{name!r} -> {tier} != {want_tier}"
        assert rec is not None, f"{name!r} -> rec is None"
    # 真实官网表外 SKU 必须 missing（不编造）
    tier, rec = _lookup(t, "培根芝士双牛堡")
    assert tier == "missing" and rec is None
    return "t12 ok"


def t13_calc_persisted():
    """13) calc 在 ingest 时持久化：stats 读到的 total_saved 必须非 0（不依赖 export 先跑）。"""
    from ledger import stats
    p = Path(tempfile.mkdtemp()) / "ledger.json"
    ingest(p, _order("A1"))
    s = stats(p)
    assert s["total_saved"] == "12.70", f"expected 12.70, got {s['total_saved']}"
    l = load(p)
    assert l["orders"]["A1"]["calc"].get("nutrition_full"), "calc.nutrition_full must persist"
    return "t13 ok"


ALL = [
    t1_dedup, t2_pricing_wording, t3_pricing_anomaly, t4_combo_no_double_count,
    t5_contradictory_rejected, t6_nutrition_disclosure, t7_personal_preserved,
    t8_corrupt_backup, t9_memory_search, t10_privacy_stripped, t11_multi_qty_not_same_minute,
    t12_customization_suffix, t13_calc_persisted,
]


if __name__ == "__main__":
    ok = 0
    for f in ALL:
        try:
            print(f())
            ok += 1
        except AssertionError as e:
            print(f"FAIL {f.__name__}: {e}")
    print(f"\n{ok}/{len(ALL)} passed")
    sys.exit(0 if ok == len(ALL) else 1)
