# 数据完整性 — 五条已知缺陷（10-22 实测）

本页是口径纪律的一部分。**任何对外输出引用数据时，必须按本页标注真实可信度。**

## 1. 营养表对 2026 新品无数据

龙焰系列 / 厚松饼 / 泷系列 等 2026 新品在官网营养表（2025-04）中不存在。
**可映射覆盖率 89.8%**（精确 40.8% + 规格映射 49.0%），真缺失项 9 个。
**对策**：票根只算成功项，明示「已匹配 N/M」；缺的标 `官方未收录`，不编造。

## 2. 数值自相矛盾（占位行）

- `无糖可口可乐`（specs 82/83/84）：kcal=0 但碳水=1（中/大杯）——物理上不成立。
- `纯悦`（spec 81）：全字段 0（占位行）。

**对策**：`nutrition.py` 自动识别并剔除矛盾行，写入 `rejected_rows` 留痕，不参与任何累加。

## 3. 官网营养数据停在 2025-04，MCP 含 2026 新品

`list-nutrition-foods` 返回 158 条，含新品；官网营养表 93 产品 / 137 规格，停在 2025-04。
**交叉核验**：35 个同名条目 100% 数值一致 → 双源可信；但**单源必漏**。
**对策**：优先 MCP 在线数据（若可用）；离线回退 `nutrition_official.json` 并标注来源。

## 4. `calculate-price` 原价虚高

实测：菜单 28 / 58 元的商品，`calculate-price` 按 58 元计入 `originalPrice`。
**对策**：**省钱账只信 `query-meals` 菜单价或订单 `totalAmount`**；`calculate-price.originalPrice` 一律不作对账基准，只作估算参考并标 ⚠️。

## 5. `calculate-price` 的 `roundList` 参数不生效

传即报 `60006`，服务端静默忽略。
**对策**：套餐必须按**主商品码整体计算**，不得走 `roundList` 分项累加。

---

## 历史查询硬限制（2026-10-22 决定性实验）

35 个工具中与订单历史相关的共 5 个，**无一支持日期/区间过滤**：

| 工具 | 入参 | 覆盖 |
|---|---|---|
| `order-list` | **零入参**，无分页无日期 | 餐品订单 |
| `query-order` | 仅 `orderId` 精确查 | 单笔详情 |
| `mall-order-list` | `lastId`+`size` 翻页（**唯一支持翻页**） | 仅积分兑换商城订单 |
| `mall-order-detail` | 仅 `orderId` | 商城订单详情 |
| `query-survey-coupon` | 仅 `orderId` | 问卷券 |

带日期参数的只有 `campaign-calendar`（查活动不查订单）。

**实验**：给 `order-list` 喂 15 种可疑参数（`startDate/endDate/startTime/endTime/beginTime/date/createTime` + `pageNum/page/pageNo/pageIndex/lastId/cursor/offset/from/start` + `orderStatus`），全部返回 `200` 且结果完全一致 —— 服务端**静默忽略**，不是 schema 层限制而是后端限制。

**含义**：MCP 不提供历史回溯。**本地账本是核心资产**：每次同步增量去重入账本，历史越攒越全；「查某一天/某段时间」走本地账本，不走 MCP。首版明示「账本积累自首次使用」，不承诺补全全年。

---

## 授权模型

鉴权：`Authorization: Bearer YOUR_MCP_TOKEN`（Streamable HTTP，`https://mcp.mcd.cn`，限流 600 次/分钟）。
Token 走手机号登录 → 控制台激活 → 同意服务协议申请，**每个用户各自申请**。

- **Skill 开源，禁内置 Token**：`mcp-config.example.json` 只放 `${MCD_MCP_TOKEN}` 占位符。
- **凭证脱敏**：账本不存 地址 / 取餐码 / 支付号；票根默认隐藏订单号 / 手机号。
- **Demo 模式**：`docs/demo/` 用离线样例账本，免 Token 体验，产出页顶标"演示数据"。
