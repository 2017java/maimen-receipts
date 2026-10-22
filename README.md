# 麦门票根册 `maimen-receipts`

> 记录你的每一单，算清每一笔，记住每一个瞬间——麦门票根册，你的麦门账本 + 记忆册。
>
> 麦当劳程序员节创意开发大赛参赛作品。**非麦当劳官方产品**，输出仅供参考，不构成医疗、营养或其他专业建议。

---

## 这是什么

把你的麦当劳真实订单变成可积累、可检索的**票根册**。每单自动生成一张「票根」：

- **吃了什么**（含套餐拆解）
- **这一单相对原价省了多少**（精确核价，不是估算）
- **营养三档标注**（实测 / 规格映射 / 官方未收录）
- **一句话补记**（"面试结束，奖励自己"）+ **一句话找回**（"找面试那天的票根"）

**1 单也能出完整票根**（不像年度回顾工具需要数据厚度）。

---

## 为什么是票根册（不是又一个"帮你省钱"工具）

榜单上"省钱 / 点单优化"已 1048 star（saver 455 + coupon 346 + budget 247）红海；"记录 / 人格 / 回顾" 878 star 也有人占位。**但没人做"票根（记录）× 核价（计算）× 一句话记忆（检索）"交叉。**

**省钱谁都会算，但把每一单记下来、算清楚、找得回，只有票根册做。**

| | saver-strategist（455） | McLife-Desk（225） | mcd-wrapped（184） | **maimen-receipts** |
|---|---|---|---|---|
| 回答的问题 | 怎么点最省 | 你是什么麦门人格 | 年度全景报告 | **你的每一单 + 省了多少 + 那天你在干嘛** |
| 数据单位 | 单次点单优化 | 年度人格 | 年度全景 | **单张票根（即时）+ 可积累** |
| 记忆 / 检索 | 无 | 无 | 无 | **一句话补记 + 一句话找回** |
| 省钱核价 | 穷举优化 | 无 | 无 | **历史订单精确核价（口径严谨）** |
| 营养 | 无 | 无 | 有 | **三档标注（精确 / 规格映射 / 未收录）** |
| 冷启动 | 需预算输入 | 需订单厚度 | 公共数据绕开 | **1 单也出完整票根** |

---

## 六步循环

```
① 导入一单        order-list → 合并列表与详情 → 去重入账本
② 生成票根        明细 + 这一单省了多少 + 营养（三档标注）+ 备注
③ 补一句话        "面试结束，奖励自己" → 写入个人记忆层（不改官方交易事实）
④ 重复同步不重复  同单导入两次仍一条；接口没返回旧单不删本地
⑤ 一句话找回      "找面试那天的票根" → 按用户真实备注检索，不猜经历
⑥ 导出票根册      月度小结（单数/支出/省下/营养 TOP）+ 票根流 + 检索入口 → 单文件 HTML
```

---

## 装 & 跑

**依赖**：纯 Python 标准库（3.10+），零第三方包。

```bash
# 1) 克隆
git clone https://github.com/2017java/maimen-receipts.git
cd maimen-receipts

# 2) 跑测试（11 条验收用例）
python skill/tests/test_ledger.py

# 3) Demo 模式（免 Token，演示数据）
python skill/core/export.py --ledger docs/demo/ledger.json --demo -o docs/outputs receipt DEMO-A1
python skill/core/export.py --ledger docs/demo/ledger.json --demo -o docs/outputs book 2026-10
# 打开 docs/outputs/receipt-DEMO-A1.html / book-2026-10.html
```

**真实订单模式**（需要自己的麦当劳 MCP Token）：

1. 申请 Token：手机号登录 `https://mcp.mcd.cn` → 控制台激活 → 同意服务协议
2. `export MCD_MCP_TOKEN=...`（**不要写进任何会被 commit 的文件**）
3. 复制 `mcp-config.example.json` → `mcp.json`（已被 `.gitignore` 屏蔽）
4. 用 MCP 拉订单 → `python skill/core/ledger.py ingest order.json`
5. 后续同 Demo 模式

---

## 必交文件

- [`README.md`](README.md) — 本文件
- [`CONTEST_DECLARATION.md`](CONTEST_DECLARATION.md) — 官方原件原样
- [`MCP_INTEGRATION.md`](MCP_INTEGRATION.md) — Server / Tool / 调用流程 / 业务价值
- [`mcp-config.example.json`](mcp-config.example.json) — 仅 `${MCD_MCP_TOKEN}` 占位符
- [`workbuddy.md`](workbuddy.md) — WorkBuddy 开发上下文

---

## 硬承诺

**省钱口径**：只写「这一单相对原价省了 ¥X」（事实陈述）。原价只信 `query-meals` 菜单价或订单 `totalAmount`；**不信 `calculate-price.originalPrice`**（实测虚高）。

**营养三档**：每个数字旁标 `精确` / `规格映射` / `官方未收录`。**钠永不反推**（腌料主导，与主料关系弱）。

**不编造**：无数据写 `官方未收录`，查不到写 `没找到`，份额不明就问。

**脱敏**：票根默认不渲染 订单号 / 手机号 / 地址 / 取餐码 / 支付号；账本不存敏感字段。

**损坏先备份**：账本 JSON 解析失败先复制到 `ledger.corrupt.<ts>.json`，**不静默清空**。

---

## 硬限制（必须知道）

| 限制 | 事实 | 影响 |
|---|---|---|
| **历史不可回溯** | 5 个订单相关 MCP 工具**无一支持日期/区间过滤**（2026-10-22 决定性实验：15 种参数喂给 `order-list` 全部被服务端静默忽略） | 「查某天/某段」**只走本地账本**；账本积累自首次使用，不承诺补全全年 |
| **营养覆盖 89.8%** | 2026 新品（龙焰/厚松饼/泷系列）官方未收录 | 票根明示 `已匹配 N/M`；缺的标 `官方未收录` |
| **calculate-price 四陷阱** | `roundList` 不生效（传即 60006）/ 历史单重算报 60006 / `originalPrice` 虚高 / 不配券 `discount=0` | 省钱账只信菜单价与订单自身金额字段 |

详细口径见 [`references/data-integrity.md`](references/data-integrity.md)。

---

## 仓库结构

```
maimen-receipts/
├── README.md                    # 本文件
├── CONTEST_DECLARATION.md       # 官方原件（一字不改）
├── MCP_INTEGRATION.md           # MCP 集成说明
├── mcp-config.example.json      # 仅环境变量占位符
├── workbuddy.md                 # WorkBuddy 开发上下文
├── SKILL.md                     # Skill 主流程（六步循环 + 硬规则）
├── .gitignore                   # 屏蔽 token / 账号数据 / 账本
├── references/
│   ├── algorithms.md            # 核价三场景 + 营养三档 算法真源
│   └── data-integrity.md        # 五条已知数据缺陷
├── skill/
│   ├── core/
│   │   ├── ledger.py            # 导入 / 去重 / 持久化 / 损坏备份
│   │   ├── pricing.py           # 省钱核价（三场景）
│   │   ├── nutrition.py         # 营养三档 + 异常剔除
│   │   ├── memory.py            # 一句话补记 / 一句话找回
│   │   └── export.py            # 票根 / 票根册 HTML（热敏纸感）
│   ├── data/
│   │   ├── nutrition_official.json   # 官网营养表（2025-04，93 产品 / 137 规格）
│   │   └── templates/
│   └── tests/
│       └── test_ledger.py       # 11 条验收用例（11/11 通过）
└── docs/
    ├── demo/ledger.json         # 免 Token 演示账本
    └── outputs/                 # 生成的票根 HTML（不入库）
```

---

## 验收用例

11 条硬验收（`skill/tests/test_ledger.py`），全部通过：

1. 同单导入两次 → 账本仍一条；不同订单不因同分钟合并
2. 省钱口径为「这一单相对原价省了 X」，原价来自订单自身金额字段
3. 未填价 / 实付大于原价 → 标 `anomaly`，不污染统计
4. 套餐父子不双算（父项跳过，只累加子项）
5. 矛盾/占位行被剔除且留痕（无糖可乐 kcal=0 但碳水=1、纯悦全字段 0）
6. 营养匹配只算成功项，票根明示「已匹配 N/M」
7. 接口未返回旧单 → 本地记录不删；个人层备注保留
8. 账本损坏 → 先备份再空态，不静默清空
9. 一句话找回；无命中 → 明说「没找到」
10. 脱敏：不存 storeAddress/pickupCode/payId
11. 多人共享单不自动算全部个人摄入

---

## 合规自检

| 红线 | 本项目 |
|---|---|
| 禁"不健康饮食"宣扬 | 不谈"你该少吃"；营养只陈述数据，不作健康建议 ✅ |
| 禁跨品牌对比 | 全程只有麦当劳 ✅ |
| 禁迷信 | 无运势 / 占卜 ✅ |
| 参赛声明 | 官方 `CONTEST_DECLARATION.md` **原样不动** ✅ |
| 凭证脱敏 | Token 只走环境变量；票根默认隐藏订单号/手机号/地址/取餐码 ✅ |
| 健康声明 | 声明"输出非医疗或营养专业建议" ✅ |
| 原创 | 自研代码；不碰官方 Logo / 摄影图 ✅ |

---

## 视觉

热敏小票 × 集章贴纸（`paper` `ink` `stamp` `mustard` `savings` 五色令牌），等宽数字，自绘 SVG，不引用官方 Logo / 菜品摄影图。

---

## 参赛声明

参赛项目为麦当劳程序员节创意开发大赛参赛作品，由参赛者独立开发，**非麦当劳官方产品**。项目输出仅供参考，不构成医疗、营养或其他专业建议；餐品信息、价格及供应状态以麦当劳官方渠道的实时结果为准。详见 [`CONTEST_DECLARATION.md`](CONTEST_DECLARATION.md)。
