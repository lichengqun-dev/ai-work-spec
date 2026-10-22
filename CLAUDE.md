# ai-work-spec — 全局上下文

> AI 助手进入本仓库时**先读本文件**。
> **三层**：`00`–`09` 是跨项目基线（通用资产，不含任何项目信息）；`projects/<项目码>/` 是项目级
> （该项目的架构、模块、模型、特有规范）；`projects/<项目码>/<需求名>/` 是业务级（该需求的产出物）。
> **冲突时：业务级 > 项目级 > 用户级。**
>
> 阶段级细节读各域 `README.md`；项目里的细节读 `projects/<项目码>/README.md`；
> 三层结构与目录约定读 `projects/README.md`。
> 本文件受 **200 行预算**约束，只放"每次都必须知道"的内容。超过预算时删减，不要扩建。

## 这是什么

AI 原生化研发知识库。承载 需求 → 设计 → 开发 → 测试 → 归档 全流程的 Skill、规范与资产，供多个项目复用。

**核心主张**：项目级规范不是一份文档，而是一次**组合**。项目只声明"选了哪些规范包 + 有哪些差异"，不复制任何共享规范的正文。

## 技术栈基线

| 维度 | 包 | 栈 | 典型项目 |
|---|---|---|---|
| 前端 | `fe-vue2-elementui` | Vue 2.6 + Element UI 2.15 + ant-design-vue 1.7 | 存量项目 |
| 前端 | `fe-vue3-elementplus` | Vue 3.5 + Element Plus 2.9 + Vite 6 + Pinia | 新项目主力 |
| 前端 | `fe-react-antd` | React 18 + antd 5 + Vite 5 | React 项目 |
| 后端 | `be-springboot2-java8` | Java 8 + Spring Boot 2.6.13 + Spring Cloud Alibaba | 存量项目 |
| 后端 | `be-springboot3-java17` | Java 17 / 21 + Spring Boot 3.x | 新项目主力 |
| 数据库 | `db-dm8` | 达梦 DM8 | 与下一项**二选一** |
| 数据库 | `db-gaussdb` | GaussDB / PostgreSQL 协议兼容 | 与上一项**二选一** |

**数据库以项目 manifest 的 `db` 声明为准，没有全局默认。** 写 SQL 前先确认目标项目选了哪个——
两个 `db` 包**互斥**，且其中多条规则**方向相反**：标识符大小写查找方向、空串与 NULL 是否等价、
有没有 `FROM DUAL`、`CONCAT` 参数个数。**选错不是"少几条约束"，而是把相反的规则注入快照**，
而模型遇到冲突会静默挑一个。

**Java 8 与 17/21 差异不只是版本号。** Java 8 下 `var` / `record` / 文本块 / `Stream.toList()` 直接编译失败；Spring Boot 2.6 用 `javax.*`，3.x 用 `jakarta.*`。写后端代码前必须确认目标项目用的是哪个包。

## 全局禁止

- 禁止跳过 **gate-03**（设计评审 + 契约冻结）直接进入编码。
- 禁止在接口契约未冻结的情况下前后端并行开发。
- 禁止在 `project.yaml` 中复制规范包条目的正文，只允许按条目编号引用。
- 禁止手工编辑 `projects/<项目码>/.agent/spec-effective/` 下的文件（由 `ai-spec-build` 生成，手改会被下次构建覆盖）。
- 禁止把域级规范（各域 `standards/`、`09_资产库/规范包/`）装回项目快照——**快照只装项目级**。
- 禁止删除 `projects/<项目码>/.agent/state/` 下已归档批次的状态文件——追溯链依赖它。
- 禁止执行任何 git 变更操作（commit / push / rebase / reset），除非用户当次明确要求。

## Skill 路由

**首选：任何研发任务都交给总入口。** 描述你要做什么即可，它判定路径并驱动全流程：

| 场景 | Skill |
|---|---|
| **任何研发任务（尤其是不确定走哪条路时）** | **`ai-flow-autopilot`** —— 说一句话即可 |
| 新需求进来（未定新建/迭代） | `ai-requirement-00-intake` |
| 从零到一的新系统（需求段编排） | `ai-requirement-autopilot` |
| 已有系统加功能 | `ai-iteration-01-impact` |
| 小改动 / 工单 | `ai-daily-01-fastlane` |
| 线上故障 | `ai-daily-02-hotfix` |
| 只是问问题（不产生任何改动） | `ai-daily-04-qa` |

知识库自身的治理（改规范、加 Skill、怀疑文档过期时）：

| 场景 | Skill |
|---|---|
| 接入新项目 / 改了规范包或 manifest | `ai-spec-build` |
| 新增、重命名、删除 Skill / 改了 description | `ai-spec-mount` |
| 改完上面任一项，或怀疑文档与实现对不上 | `ai-spec-check` |
| 项目特例要提升为共享规范 | `ai-spec-promote` |
| 改了项目级散文文档，要把约束摘成条目 | `ai-spec-extract` |

**40 个 Skill 全部已实现**，以各自 `SKILL.md` 的 `status` 字段为准。
它们已挂载到 `.claude/skills/` 下可被直接调用——**说一句话即可，不要教用户敲命令行**：
每个 Skill 的实现细节（脚本路径、参数）都在它自己的目录里，使用者不需要知道。
改动任何 Skill 定义后须重建挂载层（`ai-spec-mount`），否则模型会按过期的触发条件选 Skill。

## 规范加载顺序

**项目级进快照常驻；域级随阶段按原文加载。** 领域包与技术栈包不参与编译，也不存在层级覆盖——覆盖 / 禁用 / `frozen` / 冲突仲裁四类机制已退役（见 `ai-spec-build` 的 `references/机制退役说明.md`）。

**合并在构建期完成，不在推理期执行。** AI 不自己去读多层规范文件做合并——调用 `ai-spec-build` 生成 `projects/<项目码>/.agent/spec-effective/<项目码>.md`，然后只读那一份。理由有四条：token 成本、结果确定性、冲突可见性、可审计性。详见 `00_工作空间配置/上下文注入规范.md`。
