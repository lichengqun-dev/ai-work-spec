# 项目级 Skill（V-IPD）

> **这里放只对本项目有意义的 Skill。** 跨项目通用的 Skill 在知识库顶层 `00`–`09` 各域的
> `skills/` 下，不要放到这里。

## 判据：这个 Skill 换到另一个项目还成立吗？

| 情况 | 放哪 |
|---|---|
| 与具体业务、具体仓库、具体系统绑定 | **这里** |
| 是通用的工程做法（不管什么项目都这么做） | 顶层各域 `skills/` |
| 只在某个需求/批次里用一次 | **都不放**——那是批次产出物，放 `../<需求名>/` |

## 当前 6 个

三件套齐全（`SKILL.md` 合同 / `prompt.md` 指令 / `references/INDEX.md` 知识索引）。

| Skill | 解决什么 |
|---|---|
| [run-powerproject-backend](./run-powerproject-backend/SKILL.md) | **本地启动完整开发环境**：一期 5 服务 + 二期 7 服务 + 前端的逐步手册。JDK 8 / pathing.jar / Redis db3 / GatewayFilter / 内存策略 / 常见错误速查 |
| [run-pp-extend](./run-pp-extend/SKILL.md) | **只起二期 7 服务**（18081-18087）：pathing.jar 复用、单服务 ~11 秒、与一期混合启动的最小集 |
| [run-frontend](./run-frontend/SKILL.md) | **只起前端**（Vue 2.6，9528）：编译参数、代理矩阵全解、内存策略、包管理器 |
| [debug-full-stack](./debug-full-stack/SKILL.md) | **前后端联调与问题定位**：4 种联调模式、请求链路追踪四步、断点调试、数据库对账 |
| [replicate-from-uat](./replicate-from-uat/SKILL.md) | **一比一复刻现系统页面**：源码定位 + UAT 实测 + 双向互证 + 实现 + 视觉找茬 + 记录 |
| [vipd-refactor](./vipd-refactor/SKILL.md) | **重构期操作规范**：四层文档读取顺序 + 提交前六项自检 |

## 两类要分清楚

前四个是**当前系统怎么跑**，照着做即可。后两个描述的是**重构目标态**，
它们依赖的前置（四层 `docs/` 文档、Vue 3 目标仓、`cn.voyah.vipd` 命名空间）
**在本工作区都还不存在**——执行前必须先确认前置就位，别照着 SKILL.md 里的摘要硬写代码。

各 Skill 的 `references/INDEX.md` 里都写明了自己"依赖什么、在哪、有没有"。

## 命名

本目录用**描述性名字**（`run-frontend` / `debug-full-stack`），
与顶层 Skill 的 `ai-<域>-<序号>-<动作>` **不是同一套命名**——顶层那套是为了让
`ai-spec-mount` 生成挂载层时能机械分组，项目级 Skill 不参与挂载，所以不需要。

**本目录的 Skill 不纳入 `.claude/skills/` 挂载层。** 它们是项目本地的：
进挂载层会让项目间出现同名 Skill 互相覆盖的风险，而项目级 Skill 的适用面本来就只在项目内。

## 怎么写

与顶层 Skill 同一套三件套规范（见 `00_工作空间配置/Skill 编写规范.md`）：

```
skills/<skill-名>/
├── SKILL.md          合同：能力边界与输入输出契约
├── prompt.md         指令：可执行提示词（model-tier 注释 + 具体要求）
└── references/       知识：按需加载，默认只读 INDEX.md
```

**`references/INDEX.md` 一定要写清两件事**：这个 Skill 的操作细节在 `SKILL.md` 的哪一节（分节导航），
以及**它依赖的外部东西在哪、有没有**。后者尤其重要——依赖缺失而不写，下一个人会在执行到一半时才发现。

## 什么时候提升到顶层

某个项目级 Skill 在 **3 个以上项目**里都需要时，走 `ai-spec-promote` 的路径提升到顶层——
**不要让它长期滞留在这里**，那会让别的项目重复造一遍。