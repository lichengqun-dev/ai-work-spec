---
name: ai-spec-mount
description: 重建 .claude/skills/ 挂载层，让知识库里的 Skill 能被 Claude 发现与调用。新增、重命名、删除 Skill 或改了它们的 description 之后使用。
version: 1.0.0
stage: 00_工作空间配置
owner: 知识库 Owner
updated: 2026-10-20
applicable_stacks: []
model_tier: none
status: implemented
---

# 能力声明

把知识库里的全部 Skill **挂载**到 `.claude/skills/`，让它们能被 Claude 的 skill 发现机制看到。

同时可**校验**挂载层是否与真实定义同步——不同步就是问题，不是"下次再说"。

这是纯脚本 Skill，**不调用模型**。

## 为什么需要这一层

知识库里的 Skill 原本只是 Markdown 文件，**没有被 Claude 的 skill 机制发现**。
使用者必须知道路径、手动让 AI 去读——这正是"上手难度高"的全部来源。

Claude 靠 `.claude/skills/<name>/SKILL.md` 的 frontmatter（`name` + `description`）决定
「什么时候该用哪个 skill」。所以要让这些 Skill 真正可用，必须把它们挂到那个位置。

## 为什么是生成而不是手写

挂载层只是**指针**，真实定义仍在各域的 `skills/<name>/` 三件套里。

手写会产生 N 份需要同步的副本，**而副本一定会与真实定义分叉**——这个仓库里已经反复出现过这类问题
（README 里的条目数、域 README 里的路径、Skill 状态描述，全部是同一个病）。
所以挂载层是生成的，`description` 从真实定义里抽取。

## 输入契约

| 输入 | 来源 | 必需 | 校验规则 |
|---|---|---|---|
| 全部 Skill 真实定义 | `<域>/skills/*/SKILL.md` | 是 | 每个都须有 `name` 与 `description` |
| 仓库根目录 | 由 `CLAUDE.md` + `09_资产库/` 自动定位 | 是 | 两者都存在；否则拒绝执行 |

**`description` 是硬要求。** 缺它的 Skill 会被跳过并警告——那不是"少挂一个"，
而是这个 Skill 永远不会被任何会话看到。

## 产出契约

| 产出 | 路径 | 格式 |
|---|---|---|
| 挂载层 | `.claude/skills/<name>/SKILL.md` | 生成物，含 `name` + `description` + 指向真实定义的路径 |
| 同步性校验结果 | 输出给调用者 | 一致 / 列出不一致项 |

**挂载层要入库。** 它是 Claude 能否发现这些 Skill 的前提，不是本地产物。
（`.gitignore` 里对此有显式说明，不要把它忽略掉。）

## 前置条件（不满足则拒绝执行）

- 仓库根可定位
- 至少存在 1 个带 `name` + `description` 的 `SKILL.md`

## 执行方式

调用本 Skill 时说明要做什么即可：

| 你要做什么 | 本 Skill 的行为 |
|---|---|
| 挂载层好像过期了 / 刚加了 Skill | **重建**：按真实定义重新生成整个挂载层 |
| 只想确认是否同步（不写文件） | **校验**：逐个比对 `description` 与真实定义路径，只报不改 |

实现是一个脚本（本 Skill 目录下的 `scripts/build_claude_skills.py`），
具体参数见脚本 docstring——**使用者不需要记参数。**

## 边界（明确不做）

- **不改 Skill 的真实定义。** 只读三件套，只写 `.claude/skills/`
- **不手改挂载层。** 它是生成物；改它等于制造一份会在下次重建时消失的副本
- 不判断 Skill 的**内容**好坏。那是 `ai-spec-check` 与人的事
- 不执行 git 操作

## 失败处理

| 失败情形 | 处理 |
|---|---|
| 某 Skill 缺 `name` 或 `description` | 警告并跳过该 Skill。**说明后果**：它不会被任何会话发现 |
| 校验发现不同步 | 列出不一致项（哪些缺挂载、哪些 `description` 过期、哪些是孤儿），退出码 1 |
| 挂载层存在但知识库里已无此 Skill | 报为孤儿。重建会清掉它——**先确认那个 Skill 是真的被删了，而不是被移动了** |

## 关于"重建会清掉整个目录"

重建是**先清空 `.claude/skills/` 再重新生成**，不是增量更新。

所以：**任何手工放进 `.claude/skills/` 的东西都会消失。** 这是刻意的——
增量更新会留下"真实定义已删但挂载层还在"的孤儿，而孤儿挂载会让 Claude 调用一个不存在的 Skill。

## 何时必须调用

- 新增、重命名、删除任何 Skill 后
- 改了任何 Skill 的 `description` 后（**这是最容易忘、后果最隐蔽的一种**——挂载层的 `description` 决定模型何时选它，过期就等于按错误的条件选 Skill）
- 改了 Skill 的目录位置后
- `ai-spec-check` 报出"挂载层不同步"时
- 发版前

## 与其他 Skill 的关系

- 上游：Skill 的三件套定义
- 下游：`ai-spec-check` 会校验挂载层是否同步，形成闭环
- 同族：`ai-spec-build`（编译规范快照）、`ai-spec-check`（一致性检查）、`ai-spec-promote`（项目特例提升）——
  四个合起来是**知识库自身的治理工具**
