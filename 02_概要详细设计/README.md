# 概要详细设计

> 架构 → 功能详细设计 → 数据库设计 → 接口契约 → 前端设计。**P1 阶段交付。**

本域的核心产出是**冻结的接口契约**——它是前后端并行开发的唯一依据。契约不冻结，并行开发必然联调返工。

## 本域的 Skill

| Skill | 职责 | 说明 |
|---|---|---|
| [ai-design-01-arch](./skills/ai-design-01-arch/SKILL.md) | 架构设计与技术选型 | 整体架构、模块划分、技术选型与权衡。产出 `DEC` 编号的设计决策记录。 |
| [ai-design-02-detail](./skills/ai-design-02-detail/SKILL.md) | 功能详细设计 | 按 `FN` 编号逐节展开：时序、状态流转、异常分支。**每个 FN 一节**，这样下游才能按编号读相关段落而不读全文。 |
| [ai-design-03-db](./skills/ai-design-03-db/SKILL.md) | 数据库设计 | 表结构、索引、DDL 与回滚脚本。受 `db-dm8` 包约束（达梦方言）。 |
| [ai-design-04-api](./skills/ai-design-04-api/SKILL.md) | 接口契约设计 | 生成 OpenAPI 契约。**本步骤在 gate-03 通过后进入冻结态。** |
| [ai-design-05-frontend-spec](./skills/ai-design-05-frontend-spec/SKILL.md) | 前端页面/组件/状态设计 | 页面结构、组件拆分、状态流转设计。从原型工程迁移。 |
| [ai-design-06-review](./skills/ai-design-06-review/SKILL.md) | 设计评审执行器 | 执行 gate-03 的检查项。 |

## 依赖关系

| 上游 | `01_需求设计` 的 PRD 与原型工程 |
| 下游 | `03_编码开发` |
| 资产 | `09_资产库/规范包/` 的技术栈包、`09_资产库/领域模型/` |

## 本域的规范

| 分层架构规范 | `standards/分层架构规范.md` |
| 数据库设计规范 | `standards/数据库设计规范.md` |
| 接口设计规范 | `standards/接口设计规范.md` |
| 前端工程设计规范 | `standards/前端工程设计规范.md` |

## 状态

**P1 阶段交付。** 本域 Skill 目前均为占位实现——`SKILL.md` 已定义职责与边界，
但收到调用请求时会因前置条件（"未实现"）而拒绝执行。

**请勿在实现前调用。** 占位 `SKILL.md` 的作用是让编排层能正确判断"这个 Skill 还不能用"，
而不是让它看起来可用。
