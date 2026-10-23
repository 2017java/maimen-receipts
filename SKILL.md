---
name: maimen-receipts
description: 麦门票根册。用于导入麦当劳订单到个人账本、生成单张票根（核价 + 营养）、给订单补一句话、按关键词或日期找回旧订单、导出月度票根册。触发词：麦门票根册 / 票根 / 记一单 / 这一单省了多少 / 麦门账本 / 找那天的票根 / 麦当劳订单。离线可用：核价 / 营养 / 记忆 / 导出全部是确定性 Python，只有拉取订单需要麦当劳 MCP。
agent_created: true
---

# 麦门票根册

记录你的每一单，算清每一笔，记住每一个瞬间。

**分工纪律**：取数交给 MCP，算术交给代码，表达交给 Agent。**模型不编数字** —— 所有金额、营养、省下值由 `skill/core/*.py` 算出，Agent 只负责措辞与排版。

## 边界

| 本 Skill 负责 | 不做 |
|---|---|
| 导入 / 去重 / 持久化 / 票根 HTML / 记忆检索 | 拉取订单源（走 MCP `order-list` / `query-order`） |
| 核价（`pricing.py`） | 下单、取消、领券、兑换 |
| 营养（`nutrition.py`） | 健康建议、跨品牌对比、运势 |
| 一句话补记 / 找回（`memory.py`） | 修改官方交易事实 |

## 六步循环

| 步 | 动作 | 完成判定 |
|---|---|---|
| ① 导入 | `ledger.ingest(order_json)` | 同 `orderId` 只一条；重导不增条数 |
| ② 票根 | `export.receipt(order_id)` | HTML 落盘，且含「这一单相对原价省了 ¥X」或明确写「无法核价」 |
| ③ 补记 | `memory.note(order_id, text)` | 备注写入个人层，官方交易字段未变 |
| ④ 重同步 | 再次 `ledger.ingest` | 条数不增；接口未返回的旧单不删 |
| ⑤ 找回 | `memory.search(phrase)` | 返回命中列表；无命中时明说「没找到」，不猜 |
| ⑥ 导出 | `export.book(month)` | 单文件 HTML，含月度小结（单数 / 支出 / 省下） |

## 口径规则

- **核价**：只写「这一单相对原价省了 ¥X」。原价用订单 `totalAmount` 或 `query-meals` 菜单价；`calculate-price.originalPrice` 与菜单价存在偏差，不作核价基准。
- **营养四档**：`实测`（同名匹配）/ `实测·规格映射`（官方表有该品不同规格）/ `估算±20%`（仅当官方值缺字段时 4-4-9 反推）/ `官方未收录`（不推测、不映射近似品）。每个数字旁标档位。
- **钠永不反推**：由腌料酱料决定，与主料关系弱，缺就缺。
- **不编造**：无数据写 `官方未收录`；查不到写 `没找到`；份额不明就问，不默认全归一人。
- **脱敏**：票根不渲染订单号 / 手机号 / 地址 / 取餐码 / 支付号，仅显示订单号末四位。
- **损坏先备份**：账本解析失败先复制到 `ledger.corrupt.<ts>.json` 再空态，不静默清空。
- **Demo 隔离**：`docs/demo/` 示例账本与用户账本物理分离，产出页顶标「演示数据」。

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

- 数据来源与口径边界 → [`references/data-integrity.md`](references/data-integrity.md)
- 计算细节（核价三场景 / 营养四档算法）→ [`references/algorithms.md`](references/algorithms.md)
- MCP 调用清单与业务价值 → [`MCP_INTEGRATION.md`](MCP_INTEGRATION.md)
