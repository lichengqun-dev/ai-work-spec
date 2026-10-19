# 测试验证

> 用例生成 → 自动化 → 执行 → 回归圈定 → 测试报告。**P2 阶段交付。**

AI 增值最大的环节是**回归范围智能圈定**：从代码 diff 出发 → 映射到 FN → 从依赖图找出受影响的 FN → 映射到用例集合。

## 本域的 Skill

| Skill | 职责 | 说明 |
|---|---|---|
| [ai-test-01-cases](./skills/ai-test-01-cases/SKILL.md) | 测试用例生成 | 从 PRD + 契约 + 详细设计三者生成用例，编号挂载到 FN。 |
| [ai-test-02-automation](./skills/ai-test-02-automation/SKILL.md) | 自动化脚本生成 | 从 OpenAPI 契约自动生成接口测试脚本。 |
| [ai-test-03-execute](./skills/ai-test-03-execute/SKILL.md) | 执行与缺陷登记 | 执行用例、登记缺陷（`BUG-<批次>-<三位>`）。 |
| [ai-test-04-regression](./skills/ai-test-04-regression/SKILL.md) | 回归范围智能圈定 | 从代码 diff 出发圈定回归范围。 |
| [ai-test-05-report](./skills/ai-test-05-report/SKILL.md) | 测试报告与上线建议 | 汇总执行率、缺陷收敛、遗留风险，给出上线建议。 |

## 依赖关系

| 上游 | `03_编码开发` 的代码 + `02` 的契约与设计 |
| 下游 | `08_归档交付` |
| 资产 | `.ai/index/依赖关系图.md` |

## 本域的规范

| 测试用例设计规范 | `standards/测试用例设计规范.md` |
| 缺陷分级标准 | `standards/缺陷分级标准.md` |

## 状态

**P2 阶段交付。** 本域 Skill 目前均为占位实现——`SKILL.md` 已定义职责与边界，
但收到调用请求时会因前置条件（"未实现"）而拒绝执行。

**请勿在实现前调用。** 占位 `SKILL.md` 的作用是让编排层能正确判断"这个 Skill 还不能用"，
而不是让它看起来可用。
