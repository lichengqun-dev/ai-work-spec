# ai-work-spec — 全局上下文

> AI 助手进入本仓库时**先读本文件**。阶段级细节读各域 `README.md`；项目级细节读 `projects/<项目码>/project.yaml`。
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
| 数据库 | `db-dm8` | **达梦 DM8**（不是 MySQL） | 全部项目 |

**达梦 DM8 是默认数据库。** 任何涉及 SQL 的生成、评审、测试以 `db-dm8` 包为准，不要套用 MySQL 习惯——达梦的 CLOB、空串/NULL、模式名大小写行为都与 MySQL 有实质差异，套用会写出能编译但语义错误的 SQL。

**Java 8 与 17/21 差异不只是版本号。** Java 8 下 `var` / `record` / 文本块 / `Stream.toList()` 直接编译失败；Spring Boot 2.6 用 `javax.*`，3.x 用 `jakarta.*`。写后端代码前必须确认目标项目用的是哪个包。

## 全局禁止

- 禁止跳过 **gate-03**（设计评审 + 契约冻结）直接进入编码。
- 禁止在接口契约未冻结的情况下前后端并行开发。
- 禁止在 `project.yaml` 中复制规范包条目的正文，只允许按条目编号引用。
- 禁止手工编辑 `.ai/spec-effective/` 下的文件（由 `ai-spec-build` 生成，手改会被下次构建覆盖）。
- 禁止覆盖或禁用 `frozen: true` 的条目（构建会直接失败）。
- 禁止删除 `.ai/state/` 下已归档批次的状态文件——追溯链依赖它。
- 禁止执行任何 git 变更操作（commit / push / rebase / reset），除非用户当次明确要求。

## Skill 路由

| 场景 | Skill | 状态 |
|---|---|---|
| 新需求进来（未定新项目/迭代） | `ai-requirement-00-intake` | P0 |
| 从零到一的新系统 | `ai-requirement-autopilot` | P0 |
| 已有系统加功能 | `ai-iteration-01-impact` | P2 |
| 小改动 / 工单 | `ai-daily-01-fastlane` | P2 |
| 线上故障 | `ai-daily-02-hotfix` | P2 |
| 项目规范变更 / 新项目接入 | `ai-spec-build` | P0 |
| 项目特例要提升为共享规范 | `ai-spec-promote` | P0 |

**调用未实现的 Skill 会失败。** 各域 README 中标注了每个 Skill 的交付阶段（P0/P1/P2），状态非 P0 的尚未实现。

## 规范加载顺序

**批次特例 > 项目层 > 领域包 > 技术栈包 > 团队基线**（`frozen: true` 的条目不可被上层覆盖）。

**合并在构建期完成，不在推理期执行。** AI 不自己去读多层规范文件做合并——运行 `ai-spec-build` 生成 `.ai/spec-effective/<项目码>.md`，然后只读那一份。理由有四条：token 成本、结果确定性、冲突可见性、可审计性。详见 `00_工作空间配置/上下文注入规范.md`。
