# 知识索引 · vipd-refactor

**本 Skill 是三件套里最短的一个**——它的"知识"就是 SKILL.md 里那份检查清单与四层文档的分工表。
本目录说明**它依赖的外部知识在哪**，以及**当前有什么没就位**。

## 它依赖什么（都不在本目录）

| 依赖 | 位置 | 现状 |
|---|---|---|
| `docs/spec/` 四层文档 | 重构目标知识库 | ⚠️ **本工作区不存在** |
| `docs/constraints/tech-constraints.md` | 同上 | ⚠️ 不存在 |
| `docs/standards/coding-standard.md` | 同上 | ⚠️ 不存在 |
| `docs/guides/page-replication.md` | 同上 | ⚠️ 不存在 |
| 重构目标仓库（`cn.voyah.vipd` 命名空间） | 本地/远端 | ⚠️ 当前 `pp-powerproject-extend` 是 `com.pp` |

**这张表是刻意留在这里的。** 没有它，下一个执行本 Skill 的人会以为"读了 SKILL.md 就能开工"，
然后在第一步找不到 `docs/spec/` 时才发现。**把"依赖什么、在哪、有没有"写下来，比写一篇流程更有用。**

## 与知识库其他部分的关系

本 Skill 描述的**不是当前 V-IPD 的状态**，而是一次重构（去低码 + 服务聚合 + 换命名空间）的目标态。
判断"某条约束该按旧规矩还是新规矩"，看**本次任务属于重构前还是重构后**：

| | 旧（当前仓库） | 新（重构目标） |
|---|---|---|
| 命名空间 | `com.ak.iform.*` / `com.pp.*` | `cn.voyah.vipd.*` |
| 供应商依赖 | `com.ak.iform` / `com.aoborsoft` / `com.baomidou` | 全部移除 |
| 字段命名 | 一期带尾下划线 `id_` | 无尾下划线 |
| 逻辑删除 | 一期 `deleted_='N'` | `is_deleted` |
| 前端 | Vue 2.6 + Element UI | Vue 3 + Element Plus（见 `replicate-from-uat`） |

> **两套并行期间最容易犯的错**：在重构后的代码里用旧命名，或在旧代码里按新规范写。
> 先确认本次任务在哪一侧。

## 什么时候该在本目录新增文件

当重构的**具体操作知识**多到 SKILL.md 装不下时——例如"某个供应商包替换成什么"这类映射表。

**判据**：`replicate-from-uat` 会不会用到？会 → 放域级。
