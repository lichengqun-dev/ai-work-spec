# V-IPD 项目（岚图研发运营协同平台）

> 项目级文档。业务级（各需求）文档放本目录下的 `{需求名}/` 子目录。
> 权重：业务级 > 项目级 > 用户级（见根目录 `CLAUDE.md`）。

## 代码库

| 仓 | 说明 |
|----|------|
| `powerprojectforjava-backend` | 一期后端（iform 3.5.8，5 服务：oauth 6200 / platform 6300 / business 6305 / document 6400 / project 6500） |
| `pp-powerproject-extend` | 二期后端（Spring Boot 2.6 轻服务群，7 服务：18081-18087） |
| `powerprojectforjava-frontend` | 前端（Vue 2.6 多入口，端口 9528） |

## 文档索引

| 文档 | 说明 |
|------|------|
| [系统架构总览](./系统架构总览.md) | 整体架构、5+7 服务拓扑、技术栈、网关路由、两代后端关系 |
| [模块目录](./模块目录.md) | 35+9 个 Maven 模块职责、依赖闭包、改代码落点速查 |
| [核心业务模型](./核心业务模型.md) | 607 张表全景、一期 pp_* / 二期 extends_ 模型、核心流程、跨域关联 |
| [数据库设计规范](./数据库设计规范.md) | 两套命名风格（一期下划线后缀 / 二期无后缀）、GaussDB 特性、DDL 管理 |
| [java后端开发规范](./java后端开发规范.md) | 两期分层规范、代码落点红线、integration-layer SDK 约束 |
| [前端开发规范](./前端开发规范.md) | Vue 2.6 约定、baseUrl 路由分发、构建内存策略、常见坑 |
| [测试策略总览](./测试策略总览.md) | 分层框架（UT/FT/IT/PT/ET）、当前覆盖度、补齐路径、不引入项 |
| [测试方案-核心链路](./测试方案-核心链路.md) | 登录/一期 PM/二期冒烟/集成链路的回归基线（FT+IT） |
| [测试环境与账号管理 V1.0](./测试环境与账号管理%20V1.0.md) | core-test 账号、GaussDB 连接、本地 12 服务启动、常见错误速查 |
| [新人第一次用AI做全栈-注意事项_V1.0](./新人第一次用AI做全栈-注意事项_V1.0.md) | 三仓结构、两代后端差异、AI 协作规矩、口径优先级 |

## Skill

| Skill | 说明 |
|------|------|
| [run-powerproject-backend](./skills/run-powerproject-backend/SKILL.md) | **本地启动完整开发环境**：一期 5 服务 + 二期 7 服务 + 前端的逐步手册。JDK 8 / pathing.jar / Redis db3 / GatewayFilter / 内存策略 / 常见错误速查 |
| [run-pp-extend](./skills/run-pp-extend/SKILL.md) | **只起二期 7 服务**（18081-18087）：pathing.jar 复用、单服务 ~11 秒、与一期混合启动的最小集 |
| [run-frontend](./skills/run-frontend/SKILL.md) | **只起前端**（Vue 2.6，9528）：编译参数、代理矩阵全解、内存策略、包管理器 |
| [debug-full-stack](./skills/debug-full-stack/SKILL.md) | **前后端联调与问题定位**：4 种联调模式、请求链路追踪四步、断点调试、数据库对账 |
| [replicate-from-uat](./skills/replicate-from-uat/SKILL.md) | **一比一复刻现系统页面**：源码定位 + UAT 实测 + 双向互证 + 实现 + 视觉找茬 + 记录（**重构目标态**） |
| [vipd-refactor](./skills/vipd-refactor/SKILL.md) | **重构期操作规范**：四层文档读取顺序 + 提交前六项自检（**重构目标态**） |

> 六个都是三件套齐全（`SKILL.md` + `prompt.md` + `references/INDEX.md`），
> 且**不纳入 `.claude/skills/` 挂载层**。判据与命名约定见 [`skills/README.md`](./skills/README.md)。
>
> 后两个描述的是**重构目标态**，它们依赖的前置（四层 `docs/` 文档、Vue 3 目标仓、
> `cn.voyah.vipd` 命名空间）**在本工作区还不存在**——执行前先确认前置就位。

## 需求目录（业务级）

一个需求一个目录，放本目录下。当前：

| 需求 | 批次 | 状态 |
|---|---|---|
| [点检任务](./点检任务/) | `V-IPD-20261020-001` | 需求段完成（PRD + 原型），待进入设计 |

各需求的产出物按阶段放在 `点检任务/00_批次 ~ 05_交付/`，原型在 `点检任务/原型/`。
批次状态见 `点检任务/` 的 `CLAUDE.md` 与 `.agent/state/V-IPD-20261020-001.yaml`。

## 关键事实速查

- **JDK 8 强制**（JDK 17 mapper 静默加载失败）
- **Redis 必须 db3**（OAuth token context，用错报 REQUEST_408）
- **逻辑删除值域**：一期 `deleted_='N'`（N=正常）；二期 `is_delete=1`（1=正常，与常见约定相反）
- **一期 iform-* 模块勿改**（上游 SVN 单向同步会覆盖），定制只写 pp-* 模块
- **二期调一期只走 iform-integration-layer SDK**，不自己写 Feign
- **改配置必须同步 target/classes**（jar 是旧构建打的）
- 本地启动手册：`skills/run-powerproject-backend/SKILL.md`（本目录内，含前端构建补充）
