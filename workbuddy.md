# WorkBuddy 开发上下文 — `maimen-receipts`

> 本页说明为何 / 如何用 WorkBuddy 完成本 Skill 的开发。**面向评委与后续开发者**。

## 为什么用 WorkBuddy

WorkBuddy 把「理解需求 → 设计口径 → 实现代码 → 验收测试 → 出稿」压缩为一条工作流。
本 Skill 的开发过程是 WorkBuddy 一条流水线跑下来的：

| 阶段 | WorkBuddy 做了什么 | 落地产物 |
|---|---|---|
| 调研 | 分析 8 个榜单项目 + 4 个 MCP 工具实测 + 官网营养表交叉核验 | `references/data-integrity.md` |
| 方案 | 6 轮迭代（v1~v6）+ 3 个候选赛道（碳 / 省钱 / 记录）实证筛选 | 项目定位 "记录 + 计算 + 记忆" |
| 实现 | 按 writing-great-skills 原则写 SKILL.md + 4 个 Python 核心模块 | `skill/core/*.py` |
| 验收 | 13 条硬验收测试全部自动化，回归即跑 | `skill/tests/test_ledger.py` |
| 交付 | 5 必交文件 + 声明 + Demo 模式 + 文档 | `README.md` 等 |

## 工程纪律（写进了 skill）

1. **取数交给 MCP，算术交给代码，表达交给 Agent** —— 模型永不编数字。
2. **三档可信度标注**：精确 / 规格映射 / 官方未收录。任何数据缺失写 `官方未收录`，不编造。
3. **单一真源**：算法细节只在 `references/algorithms.md`；README / SKILL.md 只引用不复制。
4. **可回放的验收**：13 条测试覆盖去重 / 口径 / 套餐不双算 / 异常剔除 / 损坏备份 / 脱敏 / 记忆检索，新改动跑一遍即知。

## 用 WorkBuddy 复现开发

```text
提示词示例：
"基于 raw/official_nutrition.json 官网营养表，按 references/algorithms.md 三档算法
实现 skill/core/nutrition.py；异常行（kcal=0 但 carb>0.5）必须剔除并留痕；
不许反推钠；覆盖率与'已匹配 N/M'必须在 export 展示。"

WorkBuddy 会：
- 读单源（algorithms.md）而不是自己发明
- 写完自动跑 test_ledger.py 回归
- 按 SKILL.md 硬规则检查（口径纪律 / 不编造 / 脱敏）
```

## 给后续开发者的提示

- **不要在 README/SKILL.md 复制算法**：改算法只改 `references/algorithms.md`，实现改 `skill/core/*.py`。
- **不要内置 Token**：`mcp-config.example.json` 只放 `${MCD_MCP_TOKEN}` 占位符；真实 `mcp.json` 已被 `.gitignore` 屏蔽。
- **不要给营养数字加单位换算以外的修饰**：任何 "约等于" / "相当于" 必须显式标注。
- **改了核心算法必须补测试**：13 条验收用例是底线，可加不可删。

## WorkBuddy 相关链接

- WorkBuddy 文档：<https://www.workbuddy.cn/docs/workbuddy/Overview>
- 官方 Skill 写作原则：`writing-great-skills`（predictability / leading words / information hierarchy / progressive disclosure / no-op 测试）
