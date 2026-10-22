# 计算口径与算法

单一真源：本页是「怎么算」的唯一权威；`skill/core/*.py` 是实现，README / 票根只引用不重复定义。

## 一、核价三场景（pricing.py）

| 场景 | 数据源 | 算法 | 可靠性 |
|---|---|---|---|
| **历史订单核价**（主） | `query-order` 详情 | `省下 = totalAmount − realTotalAmount`（含 `totalDiscountAmount`） | ✅ 精确（同响应内字段自洽，实测 `total − discount = real`） |
| **单品当前价对比** | `query-meals` 菜单价 × 数量 vs 订单实付单价 | 逐项比 | ✅ 可靠（菜单价是公开真实价） |
| **预估下单价**（辅助） | `calculate-price` | 传主商品码算套餐价 | ⚠️ 有陷阱，必须 `query-meals` 交叉核验 |

**口径纪律**：
- ✅ 「这一单相对原价省了 ¥12.7」（事实陈述）
- ❌ 「帮你省了」（不能证明用户会按原价购买）
- ❌ 「最优价 / 最划算」（calculate-price 有陷阱，不作承诺）

**字段映射**（`query-order` 输出）：

| 语义 | 字段 |
|---|---|
| 原价合计 | `totalAmount`（decimal-string） |
| 商品原价 | `productPrice` |
| 优惠合计 | `totalDiscountAmount`（integer-string） |
| 实付 | `realTotalAmount` |
| 配送费 | `deliveryPrice` / `realDeliveryPrice` |

金额一律 `Decimal` 解析，禁止 `float`（`0.1+0.2` 问题）。原始字符串保留在 `raw` 便于审计。

## 二、营养三档（nutrition.py）

数据源：官网营养表 `skill/data/nutrition_official.json`（93 产品 / 137 规格，2025-04），14 列数组下标语义：

| 下标 | 含义 | 单位 |
|---|---|---|
| 0 | 重量 | g |
| 1 | 能量 | kJ |
| 2 | 蛋白 | g |
| 3 | 脂肪 | g |
| 4 | 碳水 | g |
| 5 | 钠 | mg |
| 10 | 胆固醇（推断） | mg |
| 11 | 糖（推断） | g |
| 13 | 钙 | mg |

> 下标 6/7/8/9/12 含义未核验，**一律不使用**（标注：未核验）。

| 档 | 场景 | 方法 | 误差 |
|---|---|---|---|
| **精确** | 名称精确同名匹配 | 直接读表 | ≈ 0 |
| **估算±20%** | 同主料换酱 | 4-4-9 反推：能量 ≈ 蛋白×4 + 碳水×4 + 脂肪×9（kcal） | **−1.6%**（官方数据自洽，实测） |
| **官方未收录** | 全新基底 / 缺失项 | **不编造**，标 `官方未收录` | — |

**钠永不反推**：由腌料 / 酱料决定，与主料关系弱，缺就缺。

**套餐累加**：父项（套餐）与子项（`comboItemList`）**不得双算** —— 只累加子项；父项仅作展示标签。

**异常行剔除**（写入 `rejected_rows` 留痕）：
- kcal=0 但 碳水>0.5（物理矛盾，如无糖可乐中/大杯）
- 全字段 0（占位行，如纯悦）

**覆盖率披露**：每张票根尾部标 `已匹配 N/M 项`，N=精确+估算，M=订单商品总数（去套餐父项）。

## 三、记忆检索（memory.py）

- 数据：本地账本 `personal.note` / `personal.tags`（**只改个人层，不动官方交易层**）
- 检索：关键词匹配（大小写 / 全半角归一后子串匹配）+ 日期（`YYYY-MM-DD` / `YYYY-MM` / `本月` / `上周`）+ 金额（`¥X` / `省了X`）
- 不猜经历：query 命中不了就 `没找到`，**禁止**用 LLM 推断"你大概在加班"

## 四、账本格式（ledger.py）

```json
{
  "version": 1,
  "updated_at": "2026-10-22T20:00:00",
  "orders": {
    "<orderId>": {
      "official": {
        "orderId": "...", "createTime": "...", "storeName": "...",
        "orderStatus": "...", "items": [ {"name":"...","qty":1,"price":"23.9","combo":[...]} ],
        "totalAmount": "36.6", "realTotalAmount": "23.9",
        "totalDiscountAmount": "12.7", "source": "query-order"
      },
      "calc": {
        "saved": "12.7", "saved_pct": "34.7",
        "nutrition": {"energy_kj":1234, "protein":20, "fat":15, "carb":40, "sodium":800},
        "nutrition_tier": "exact|estimated|missing",
        "matched_items": 3, "total_items": 4,
        "rejected_rows": []
      },
      "personal": {"note": "", "tags": [], "would_reorder": null},
      "privacy": {"orderId_masked": "****1234"}
    }
  }
}
```

**唯一键**：`orderId`。**幂等**：同 `orderId` 再次 ingest 只覆盖 `official` 快照，**保留 `personal`**，`calc` 重算。
