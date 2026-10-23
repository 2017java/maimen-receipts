# MCP 集成说明

> Server：麦当劳中国官方 MCP `https://mcp.mcd.cn`（Streamable HTTP）
> 鉴权：`Authorization: Bearer ${MCD_MCP_TOKEN}`
> 限流：600 次/分钟

---

## 一、使用的 MCP Server

| 项 | 值 |
|---|---|
| 协议 | Model Context Protocol，Streamable HTTP |
| 端点 | `https://mcp.mcd.cn` |
| 协议版本 | `2025-03-26` |
| Server 标识 | `mcd-mcp` v1.0.0 |
| 鉴权 | Bearer Token，环境变量 `MCD_MCP_TOKEN` |

Token 由每位用户自行申请：手机号登录 → 控制台激活 → 同意服务协议。本项目不内置、不托管任何 Token，配置模板见 [`mcp-config.example.json`](mcp-config.example.json)。

---

## 二、使用的 Tool（5 个，全部只读）

| Tool | 用途 | 入参 | 关键输出字段 |
|---|---|---|---|
| `order-list` | 拉取历史订单列表 | 无 | `orderId`、`createTime`、`storeName`、`orderStatus`、`orderProductList[]`、`realTotalAmount` |
| `query-order` | 拉取单笔订单详情（核价依据） | `orderId` | `totalAmount`、`realTotalAmount`、`totalDiscountAmount`、`productPrice`、`orderProductList[].price` |
| `query-meals` | 查询当前菜单价（核价参照） | `storeCode`、`orderType`、`beType` | 当前门店菜单价目 |
| `list-nutrition-foods` | 营养数据补充 | 无 | 158 条：能量 / 蛋白 / 脂肪 / 碳水 / 钠 |
| `available-coupons` | 券优惠补充（仅当订单 `discount=0` 时） | 订单上下文 | 可用券列表 |

**不使用的 Tool**：`create-order`、`cancel-order`、`auto-bind-coupons`、`draw-lottery`、`mall-create-order`、`party-order-create`、`delivery-create-address` —— 本 Skill 定位为只读记账工具，不执行任何下单、取消、领券、兑换等写操作。

---

## 三、调用流程

```
[1] order-list（无入参）
      ↓  拿到订单列表：orderId / createTime / storeName / 商品 / 实付
[2] query-order(orderId)
      ↓  补全金额字段：totalAmount / totalDiscountAmount / productPrice
[3] ledger.ingest()
      ↓  以 orderId 为唯一键去重入账本；同单重复导入不产生新记录
[4] query-meals(storeCode)
      ↓  取当前菜单价，作为单品对比参照
[5] pricing.audit_order()  +  nutrition.compute()
      ↓  核价：省下 = totalAmount − realTotalAmount
      ↓  营养：套餐拆子项，逐项匹配官方表并标可信度
[6] export.receipt() / export.book()
      ↓  渲染票根 / 月度票根册 HTML
```

**幂等性**：步骤 [3] 对同一 `orderId` 重复执行只覆盖官方交易快照并重算派生数据，个人备注原样保留。

**历史范围说明**：`order-list` 不提供日期区间过滤参数，`query-order` 仅按 `orderId` 精确查询。因此「查某天 / 某段时间」由本地账本承担，账本自首次使用起积累。

---

## 四、业务价值

| 用户场景 | 没有 MCP 时 | 接入 MCP 后 |
|---|---|---|
| 想知道这个月花了多少、省了多少 | 只能逐单在 App 里翻，无法汇总 | `order-list` 拉全量 + 本地账本持久化，跨月可查 |
| 想知道这一单到底省了多少 | 说不清原价与实付的对应关系 | `query-order` 金额字段同响应自洽，可精确做差 |
| 想知道套餐一共吃了多少热量 | 套餐营养拆不开，只能查单品 | 拆 `comboItemList` 子项，逐项匹配官方营养表 |
| 想记住「那天为什么吃这顿」 | 无处记录 | 订单 + 一句话备注绑定，日后可检索 |
| 想回顾自己的消费与饮食轨迹 | 无积累，App 不提供导出 | 月度票根册单文件 HTML 可导出保存 |

**核心价值**：把 MCP 提供的**一次性查询**，转化为**可积累、可检索的个人资产**。

---

## 五、数据来源与边界

| 项 | 说明 |
|---|---|
| 订单数据 | 来自 `order-list` + `query-order`，字段完整（订单号 / 时间 / 门店 / 商品 / 金额 / 状态） |
| 核价依据 | 订单自身 `totalAmount` − `realTotalAmount`；菜单价来自 `query-meals` |
| 营养数据 | 官方营养表 `skill/data/nutrition_official.json`（93 产品 / 137 规格）；MCP `list-nutrition-foods` 作双源交叉核验，35 个同名条目数值完全一致 |
| 营养覆盖 | 官方未收录的品项标 `官方未收录`，不推测、不映射近似品；票根明示 `已匹配 N/M 项` |
| 下单预估接口 | 本 Skill 不以 `calculate-price` 的 `originalPrice` 作为核价基准，仅作可选估算参考（详见 [`references/data-integrity.md`](references/data-integrity.md)） |
| 隐私字段 | 账本不保存地址、取餐码、支付号；票根仅显示订单号末四位 |

---

## 六、合规

- 只读：不调用任何写操作接口
- 凭证：Token 仅从环境变量读取，仓库内无任何真实凭证
- 脱敏：生成的票根默认不渲染订单号、手机号、地址、取餐码、支付号
- 声明：输出非医疗或营养专业建议；餐品信息、价格及供应状态以麦当劳官方渠道实时结果为准
