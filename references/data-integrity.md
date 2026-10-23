# 数据来源与口径说明

本页说明各项数据的来源、已知边界，以及本 Skill 采取的应对方式。**任何对外输出引用数据时，按本页标注可信度。**

---

## 一、数据来源

| 数据 | 来源 | 版本 / 规模 |
|---|---|---|
| 订单交易 | MCP `order-list` + `query-order` | 实时，绑定用户本人账号 |
| 菜单价 | MCP `query-meals` | 当前门店实时价目 |
| 营养 | 官方营养表 `skill/data/nutrition_official.json` | 93 产品 / 137 规格 |
| 营养（在线） | MCP `list-nutrition-foods` | 158 条 |

**双源交叉核验**：官网营养表与 MCP `list-nutrition-foods` 的 35 个同名条目，数值 100% 一致。两源可信，但**单源会漏**（见下）。

---

## 二、已知边界与应对

### 1. 营养表未覆盖部分新上市产品

官方营养表的收录范围不含部分 2026 年新上市品项。以订单实际商品统计，**可映射覆盖率 89.8%**（精确匹配 40.8% + 规格映射 49.0%），未覆盖 9 项。

**应对**：票根只累加成功匹配的项，并明示 `已匹配 N/M 项`。未覆盖的标 `官方未收录`，**不推测、不用近似品替代**。

### 2. 个别记录为占位行

官方表中存在少量占位记录，数值不自洽：

- `无糖可口可乐`（中 / 大杯）：能量 0 kJ 但碳水 1 g
- `纯悦`：全字段为 0

**应对**：`nutrition.py` 识别并剔除矛盾行，写入 `rejected_rows` 留痕，不参与任何累加。

### 3. 两源收录范围不同

官网营养表与 MCP `list-nutrition-foods` 的收录范围不一致（后者含更多新上市品项）。

**应对**：在线数据可用时优先使用；离线回退内置营养表并标注来源。

### 4. 下单预估接口的原价字段与菜单价存在偏差

实测中，`calculate-price` 返回的 `originalPrice` 与 `query-meals` 菜单价不一致（示例：菜单价 28 / 58 元的商品，预估接口按 58 元计入原价）。

**应对**：核价**只使用订单自身金额字段或 `query-meals` 菜单价**。`calculate-price.originalPrice` 不作核价基准，如使用仅作估算参考。

### 5. `calculate-price` 的 `roundList` 参数不生效

传入该参数返回错误码 `60006`。

**应对**：套餐按**主商品码整体计算**，不走 `roundList` 分项累加。

---

## 三、订单查询的能力边界

MCP 中与订单相关的 5 个 Tool 均不支持按日期区间过滤：

| Tool | 入参 | 覆盖范围 |
|---|---|---|
| `order-list` | 无入参 | 餐品订单 |
| `query-order` | 仅 `orderId` | 单笔详情 |
| `mall-order-list` | `lastId` + `size`（唯一支持翻页） | 积分兑换商城订单 |
| `mall-order-detail` | 仅 `orderId` | 商城订单详情 |
| `query-survey-coupon` | 仅 `orderId` | 问卷券 |

带日期参数的只有 `campaign-calendar`（查活动，不查订单）。

**验证方式**：向 `order-list` 传入 7 种日期类参数（`startDate` / `endDate` / `startTime` / `endTime` / `beginTime` / `date` / `createTime`）与 9 种分页类参数（`pageNum` / `page` / `pageNo` / `pageIndex` / `lastId` / `cursor` / `offset` / `from` / `start`）及 `orderStatus`，共 15 种，响应均为 200 且返回结果完全一致 —— 这些参数不被服务端处理，属接口能力边界。

**应对**：**本地账本是核心资产**。每次同步增量去重写入账本，历史随使用积累；「查某一天 / 某段时间」由本地账本承担。首次使用时明示「账本积累自首次使用」，不承诺补全历史订单。

---

## 四、授权与隐私

鉴权方式：`Authorization: Bearer ${MCD_MCP_TOKEN}`（Streamable HTTP，限流 600 次/分钟）。
Token 由每位用户自行申请，**本项目不内置任何 Token**。

- **配置模板**：`mcp-config.example.json` 仅含 `${MCD_MCP_TOKEN}` 占位符
- **账本脱敏**：不保存地址、取餐码、支付号
- **票根脱敏**：默认不渲染订单号、手机号、地址、取餐码、支付号，仅显示订单号末四位
- **Demo 模式**：`docs/demo/` 使用离线示例账本，免 Token 体验，产出页顶标「演示数据」
