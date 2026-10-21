---
name: ai-spec-build
description: 把多层规范（基线/技术栈包/领域包/项目层）编译成单一生效快照。当接入新项目、改了规范包或 manifest、或需要确认某个项目该遵守哪些规范时使用。
version: 0.1.0
stage: 00_工作空间配置
owner: 知识库 Owner
updated: 2026-10-19
applicable_stacks: []
model_tier: none
status: implemented
---

# 能力声明

把多层规范（团队基线 / 技术栈包 / 领域包 / 项目层）**编译成单一「生效规范快照」**。

这是纯脚本 Skill，**不调用模型**——合并结果必须可复现、可 diff、可审计。

## 输入契约

| 输入 | 来源 | 必需 | 校验规则 |
|---|---|---|---|
| 项目 manifest | `projects/<项目码>/.agent/project.yaml` | 是 | `project` 字段须与目录名一致 |
| 项目级条目（提炼） | `projects/<项目码>/.agent/rules/*.md` | 否 | 条目前缀须为 `STD-PRJ-<项目码大写>-`；frontmatter 的 `source_hash` 与源文档比对 |
| 项目级条目（内联） | manifest 的 `project_only` | 否 | 同上 |
| 规范包 | `09_资产库/规范包/{stacks,domains}/*/PACK.md` | 是 | frontmatter 必填字段齐全 |
| 团队基线 | `<业务域>/standards/**/*.md` | 否 | 条目前缀须为 `STD-BASE-` |

> **项目根的散文文档不是本 Skill 的输入。** 它们由 `ai-spec-extract` 摘成条目后才进快照——
> 本 Skill **不理解散文**，也不会去猜哪句话是约束。

## 产出契约

| 产出 | 路径 | 格式 |
|---|---|---|
| 生效规范快照（人读） | `projects/<项目码>/.agent/spec-effective/<项目码>.md` | Markdown，分 A/B/C/D 四段 |
| 生效规范快照（机读） | `projects/<项目码>/.agent/spec-effective/<项目码>.json` | JSON，含逐条来源链 |
| 执行日志 | `projects/<项目码>/.agent/logs/spec-build.jsonl` | 追加一行 JSON |

## 执行方式

调用本 Skill 时说明要做什么即可：

| 你要做什么 | 本 Skill 的行为 |
|---|---|
| 接入新项目 / 改了规范包或 manifest | **编译**该项目的快照，并做全部校验 |
| 一次重建所有项目 | **编译全部** |
| 只想知道有没有问题，不写文件（CI 用） | **只校验** |
| 想知道有哪些包可选、包里各有多少条 | **列出包与版本** |

实现是一个脚本（本 Skill 目录下的 `scripts/spec_build.py`），参数说明见脚本 docstring——
**使用者不需要记参数。** 依赖 Python 3.8+ 与 PyYAML；缺 PyYAML 时本 Skill **拒绝执行并说明**，
不会退化成"编译失败就当通过"。

## 前置条件（不满足则拒绝执行）

- `CLAUDE.md` 与 `09_资产库/` 均存在（脚本据此定位仓库根目录）
- 目标项目的 `project.yaml` 存在且 `project` 字段与目录名一致
- **任一校验项失败即整体失败，不生成任何文件**（不产生"半成品快照"）

## 校验项（任一失败即中止）

1. `PACK.md` frontmatter 必填字段齐全，`files` 列出的文件都存在
2. 条目前缀与所在包的 `prefix` 一致
3. 条目编号在全库范围内唯一
4. manifest 引用的包与版本存在且匹配（版本锁定，升级需显式改 manifest）
5. `overrides` 引用的条目存在
6. 对 `frozen` 条目的 override / disable / append 一律拒绝
7. `disable` 必须带 `expires`；禁用基线或包条目还需 `approved_by`
8. 同层冲突且未在 manifest 的 `domains` 中声明优先级

## 边界（明确不做）

- **不修改任何规范内容。** 只读包与 manifest 与 rules，只写 `projects/<项目码>/.agent/spec-effective/` 与 `projects/<项目码>/.agent/logs/`
- **不从散文文档里提取条目。** 那是 `ai-spec-extract` 的事。本 Skill 只认已经带编号的条目
- **不因漂移而失败。** 源文档变了就报「已变更」，但快照照常产出（改文档是常态）
- 不自动升级包版本。包升级必须由人改 manifest
- 不自动"修复"冲突。冲突一律以失败告终，裁决由人做
- 不检查条目正文的语义矛盾（无法机械判定），只处理显式声明的 `conflicts_with`
- 不调用模型

## 失败处理

| 失败情形 | 处理 |
|---|---|
| 校验失败 | 打印具体条目 ID、来源文件、失败原因，退出码 1，不写文件 |
| **源文档已变更（漂移）** | **不失败**。告警同时写进 stderr 与**快照正文顶部**，并在 JSON 的 `rules_drift` 里列出。处理是调用 `ai-spec-extract` 重新提炼 |
| 项目根有看似条目头却不会被解析的行 | 告警列出具体文件与行号，**不失败**。提示改用 `ai-spec-extract` |
| A 段超过 120 行预算 | 打印警告但**不失败**（提示有非硬约束条目被打成了 resident） |
| 项目级条目超过 30 条 | 在快照 D 段标注警告，建议运行 `ai-spec-promote` |
| 仓库根目录定位失败 | 退出码 2，提示用 `--repo` 显式指定 |

## 何时必须调用

- 新增项目接入后
- 修改任何规范包条目后
- 修改项目 manifest（选包、override、project_only）后
- 批次启动前（确保快照与当前规范一致）
- CI 中作为门禁（用 `--check`）

## 与其他 Skill 的关系

- 上游：无。本 Skill 是地基
- 下游：所有读规范的 Skill（`ai-design-*`、`ai-dev-*`、`ai-test-*`）依赖它产出的快照
- 配套：`ai-spec-promote` 负责把项目特例提升为共享包条目