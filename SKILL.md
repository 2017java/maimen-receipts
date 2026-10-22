---
name: maimen-receipts
description: Use when the user asks to import McDonalds China orders into a personal receipt book, generate a per-order receipt (savings + nutrition), add a one-line note to an order, find an old order by phrase or date, or export a monthly receipt book. Triggers: 麦门票根册 / 票根 / 记一单 / 这一单省了多少 / 麦门账本 / 找那天的票根 / 麦当劳订单. Knowledge cutoff: offline core (ledger/pricing/nutrition/memory/export) is deterministic Python; live McDonalds MCP is only needed to *fetch* orders — skill works fully offline on a pre-existing ledger.
agent_created: true
---

# maimen-receipts — 麦门票根册

记录你的每一单，算清每一笔，记住每一个瞬间。

**分工纪律（不可破）**：取数交给 MCP，算术交给代码，表达交给 Agent。**模型永不编数字** —— 所有金额、营养、省下值由 `skill/core/*.py` 算出，Agent 只负责措辞与排版。

## 边界

| Skill 内 | Skill 外 |
|---|---|
| 导入 / 去重 / 持久化 / 票根 HTML / 记忆检索 | 订单源获取（MCP `order-list` / `query-order`） |
| 省钱核价（`pricing.py`） | 下单、取消、领券、兑换（**一律拒绝**） |
| 营养三档（`nutrition.py`） | 任何健康建议 / 跨品牌对比 / 运势（**一律拒绝**） |
| 一句话补记 / 找回（`memory.py`） | 修改官方交易事实（**一律拒绝**） |

## 六步循环

| 步 | 动作 | 完成判定 |
|---|---|---|
| ① 导入 | 调 `ledger.ingest(order_json)` | 账本里新增条数 = 去重后条数；同 orderId 只一条 |
| ② 票根 | 调 `export.receipt(order_id)` | HTML 落盘；**每张票根含"这一单相对原价省了 ¥X"或明确写"无法核价"** |
| ③ 补记 | 调 `memory.note(order_id, text)` | 备注写入 personal 层；官方交易层字段未被改动 |
| ④ 重同步 | 再次 `ledger.ingest` | 条数不增；接口未返回的旧单**不删** |
| ⑤ 找回 | 调 `memory.search(phrase)` | 返回命中票根 id 列表；无命中时**明说"没找到"**，不猜 |
| ⑥ 导出 | 调 `export.book(month)` | 单文件 HTML；含月度小结（单数/支出/省下/营养 TOP） |

## 硬规则

- **省钱口径**：只写「这一单相对原价省了 ¥X」。原价来源只信 `query-meals` 菜单价或订单 `totalAmount`；**不信 `calculate-price.originalPrice`**（实测虚高：菜单 28/58，算价按 58 计）。
- **营养三档**：`精确`（同名累加）/ `估算±20%`（4-4-9 反推）/ `官方未收录`。**钠永不反推**（腌料主导，与主料关系弱）。每个数字旁标档位。
- **不编造**：无数据就写 `官方未收录`；查不到就写 `没找到`；份额不明就问，不默认全部归一人。
- **脱敏**：票根默认不渲染 订单号/手机号/地址/取餐码/支付号；导出前自检一遍。
- **损坏先备份**：账本 JSON 解析失败 → 复制到 `ledger.corrupt.<ts>.json` 再空态，**不静默清空**。
- **Demo 隔离**：`docs/demo/` 样例账本物理独立于用户账本，任何产出页顶标"演示数据"。

## 调用方式

```bash
# 1) 喂单（MCP order-list / query-order 的原始 JSON 均可）
python skill/core/ledger.py ingest path/to/order.json

# 2) 出票根
python skill/core/export.py receipt <order_id> -o docs/outputs/

# 3) 补一句
python skill/core/memory.py note <order_id> "面试结束，奖励自己"

# 4) 找回
python skill/core/memory.py search "面试"

# 5) 出册
python skill/core/export.py book 2026-10 -o docs/outputs/
```

每条命令均输出 JSON 到 stdout。**完成判定**：stdout 的 `ok:true`，且产出文件路径非空。

## 进阶

- 数据口径与已知数据缺陷 → [`references/data-integrity.md`](references/data-integrity.md)
- 计算细节（核价三场景 / 营养三档算法）→ [`references/algorithms.md`](references/algorithms.md)
- MCP 调用清单与陷阱 → 仓库根 `MCP_INTEGRATION.md`
