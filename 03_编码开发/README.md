# 编码开发

> 工程骨架 → 后端实现 → 前端实现 → 单元测试 → 代码评审 → 文档回流。**P1 阶段交付。**

核心约束：按 `FN` 编号逐个交付，提交信息必须带 FN 编号。这是追溯链的最后一环。

## 本域的 Skill

| Skill | 职责 | 说明 |
|---|---|---|
| [ai-dev-01-scaffold](./skills/ai-dev-01-scaffold/SKILL.md) | 工程骨架与模块划分 | 依据架构设计生成工程骨架、目录结构、模块划分。 |
| [ai-dev-02-backend](./skills/ai-dev-02-backend/SKILL.md) | 后端功能实现 | 按 `FN` 逐个实现。**技术细节从生效规范快照读**，不在本 Skill 中硬编码。 |
| [ai-dev-03-frontend](./skills/ai-dev-03-frontend/SKILL.md) | 前端实现与联调 | 从原型工程迁移，基于冻结契约联调。 |
| [ai-dev-04-unittest](./skills/ai-dev-04-unittest/SKILL.md) | 单元测试与覆盖率补齐 | 生成单测、补齐未覆盖分支。 |
| [ai-dev-05-codereview](./skills/ai-dev-05-codereview/SKILL.md) | 代码评审执行器 | 执行 gate-04 检查项，含契约一致性校验。 |
| [ai-dev-06-docsync](./skills/ai-dev-06-docsync/SKILL.md) | 代码变更回流文档 | 代码改了但文档没改时，自动回写文档变更。 |

## 依赖关系

| 上游 | `02_概要详细设计` 的冻结契约与详细设计 |
| 下游 | `04_测试验证` |
| 资产 | `09_资产库/组件库/` |

## 本域的规范

| 后端编码规范 | `standards/后端编码规范.md` |
| 前端编码规范 | `standards/前端编码规范.md` |
| 提交信息与分支规范 | `standards/提交信息与分支规范.md` |
| 单元测试规范 | `standards/单元测试规范.md` |

## 状态

**P1 阶段交付。** 本域 Skill 目前均为占位实现——`SKILL.md` 已定义职责与边界，
但收到调用请求时会因前置条件（"未实现"）而拒绝执行。

**请勿在实现前调用。** 占位 `SKILL.md` 的作用是让编排层能正确判断"这个 Skill 还不能用"，
而不是让它看起来可用。
