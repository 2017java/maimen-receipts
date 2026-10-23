# WorkBuddy 开发上下文

本文件说明本项目如何用 WorkBuddy 完成开发，供评审核验 WorkBuddy 专项使用。

---

## 使用方式

Skill 装好后，在 WorkBuddy 里用自然语言直接调用，无需记命令：

```
导入我的麦当劳订单，出一张票根
这一单省了多少？
给 9 月 21 号那单补一句：面试结束，奖励自己
找面试那天的票根
出 9 月的票根册
```

Agent 读取根目录 `SKILL.md` 后按六步循环执行；所有金额与营养数字由 `skill/core/*.py` 计算，模型只负责措辞与排版。

---

## 开发流程

| 阶段 | WorkBuddy 承担的工作 | 落地产物 |
|---|---|---|
| 数据核验 | 实调 MCP 工具、交叉核验官网营养表 | `references/data-integrity.md` |
| 口径设计 | 确定核价算法、营养可信度分级、边界处理 | `references/algorithms.md` |
| 实现 | 按 Skill 写作原则编写 `SKILL.md` + 5 个 Python 模块 | `skill/core/*.py` |
| 验收 | 13 条自动化验收用例，改动即回归 | `skill/tests/test_ledger.py` |
| 交付 | 项目文档 + Demo 模式 + 参赛材料 | `README.md` 等 |

---

## 工程约束

1. **取数交给 MCP，算术交给代码，表达交给 Agent** —— 模型不编数字。
2. **四档可信度标注**：`实测` / `实测·规格映射` / `估算±20%` / `官方未收录`。缺失一律标 `官方未收录`，不推测。
3. **单一真源**：算法只在 `references/algorithms.md` 定义；`README.md` 与 `SKILL.md` 只引用不复制。
4. **可回放的验收**：13 条测试覆盖去重、核价口径、套餐父子不双算、异常行剔除、损坏备份、脱敏、记忆检索命中与未命中、定制后缀匹配、派生数据持久化。

---

## 复现示例

```text
提示词：
"基于 skill/data/nutrition_official.json 官方营养表，按 references/algorithms.md 的四档算法
实现 skill/core/nutrition.py。要求：
 - 异常行（能量 0 但碳水 > 0.5）必须剔除并写入 rejected_rows
 - 钠不反推
 - 票根必须展示 '已匹配 N/M 项'
 - 不推测、不用近似品替代未收录项"
```

WorkBuddy 会以 `references/algorithms.md` 为唯一口径来源实现，写完自动跑 `test_ledger.py` 回归，并按 `SKILL.md` 的口径规则自检。

---

## 后续开发注意事项

- **算法改动只改一处**：`references/algorithms.md` 定口径，`skill/core/*.py` 落实现，不要在 README / SKILL.md 复制算法描述。
- **不内置任何凭证**：`mcp-config.example.json` 仅含 `${MCD_MCP_TOKEN}` 占位符。
- **营养数字不加额外修辞**：除单位换算外，任何「约等于」「相当于」必须显式标注为估算。
- **核心算法改动必须补测试**：13 条是底线，可加不可删。

---

## 相关链接

- WorkBuddy 文档：<https://www.workbuddy.cn/docs/workbuddy/Overview>
- Skill 写作原则：`writing-great-skills`（predictability / leading words / information hierarchy / progressive disclosure）
