# maimen-receipts · MCP 集成说明

> 目标 Server：麦当劳中国官方 MCP `https://mcp.mcd.cn`（Streamable HTTP）
> 限流：600 次/分钟 ｜ 鉴权：`Authorization: Bearer ${MCD_MCP_TOKEN}`

## 1. 鉴权与 Token（**每用户自己申请，禁内置**）

1. 手机号登录 → 控制台激活
2. 同意《服务协议》
3. 取得 MCP Token，导出为环境变量 `MCD_MCP_TOKEN`

配置模板见 [`mcp-config.example.json`](mcp-config.example.json)（**仅占位符，绝无真 token**）。
未配 Token 也可运行 —— 用 `docs/demo/` 离线样例账本走 **Demo 模式**（产出页顶标"演示数据"）。

## 2. 实际使用的 MCP 工具（5 个，全部只读）

| 工具 | 用途 | 关键入参 | 关键输出 |
|---|---|---|---|
| `order-list` | 拉历史订单列表 | **零入参** | `data.list[]`：`orderId/createTime/storeName/orderStatus/orderProductList[].{productName,quantity,comboItemList[]}/realTotalAmount` |
| `query-order` | 拉单笔详情（核价） | `orderId` | `totalAmount/realTotalAmount/totalDiscountAmount/productPrice/deliveryPrice/realDeliveryPrice/orderProductList[].price` |
| `query-meals` | 菜单价（核价基准） | `storeCode, orderType, beType` | 当前门店菜单价目 |
| `list-nutrition-foods` | 营养表（离线兜底） | 零入参 | 158 条能量/蛋白/脂肪/碳水/钠 |
| `available-coupons` | 券优惠补充（仅在 `discount=0` 时） | 订单上下文 | 可用券列表 |

**明确不使用 / 拒绝调用**（属于"写"或不可靠）：
`create-order` / `cancel-order` / `auto-bind-coupons` / `draw-lottery` / `mall-create-order` / `party-order-create` / `delivery-create-address` / `calculate-price.originalPrice`（虚高，不作对账基准）

## 3. 调用流程（六步循环对应的取数链路）

```
[1] order-list (零入参)  → 拿到订单列表（含 createTime/store/items/realTotalAmount）
       ↓ 合并
[2] query-order(orderId) → 补 totalAmount/totalDiscountAmount/productPrice 等金额明细
       ↓
[3] ledger.ingest()      → 去重入账本（唯一键 orderId；同单重导不重复）
       ↓
[4] query-meals(storeCode) → 菜单价，用于"单品当前价对比"档
       ↓
[5] pricing.audit_order() → 省下 = totalAmount − realTotalAmount
    nutrition.compute()   → 三档营养（缺则 `官方未收录`）
       ↓
[6] export.receipt() / export.book() → 票根 / 票根册 HTML
```

**幂等**：步骤 [3] 重复执行同 orderId，`personal.note` 保留，只覆盖 `official` 快照并重算 `calc`。

## 4. 业务价值（为何用 MCP）

| 痛点 | MCP 解决方式 | 价值 |
|---|---|---|
| 订单散在 App 里，查不到历史 | `order-list` + 本地账本持久化 | 一次性沉淀，跨月可查 |
| 不知道这一单到底省了多少 | `query-order` 的 `totalAmount`/`realTotalAmount` 同响应自洽 | **精确核价**，无需估算 |
| 套餐营养说不清 | `list-nutrition-foods` 精确同名匹配 | 三档可信度标注，不编造 |
| 想不起"那天吃了啥" | 本地 `personal.note` + 检索 | 一句话找回 |
| 月度花了多少、省了多少 | 账本派生 `export.book(month)` | 票根册月度小结 |

## 5. 硬限制（**必须向用户明示**）

- **历史不可回溯**：5 个订单相关工具**无一支持日期/区间过滤**（2026-10-22 实测：15 种参数喂给 `order-list` 全部被服务端静默忽略）。**"查某天/某段"只走本地账本**，账本积累自首次使用，不承诺补全全年。
- **营养覆盖 89.8%**：2026 新品（龙焰/厚松饼/泷系列）官方未收录，票根明示 `已匹配 N/M`。
- **calculate-price 四陷阱**：`roundList` 不生效（传即 60006）/ 历史单重算报 60006 / `originalPrice` 虚高 / 不配券 `discount=0`。**省钱账只信菜单价与订单自身金额字段**。

详细口径见 [`references/data-integrity.md`](references/data-integrity.md)。
