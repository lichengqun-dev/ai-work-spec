---
name: ai-spec-build
version: 0.1.0
stage: 00_工作空间配置
owner: 知识库 Owner
updated: 2026-10-19
applicable_stacks: []
model_tier: none
---

# 能力声明

把多层规范（团队基线 / 技术栈包 / 领域包 / 项目层）**编译成单一「生效规范快照」**。

这是纯脚本 Skill，**不调用模型**——合并结果必须可复现、可 diff、可审计。

## 输入契约

| 输入 | 来源 | 必需 | 校验规则 |
|---|---|---|---|
| 项目 manifest | `projects/<项目码>/project.yaml` | 是 | `project` 字段须与目录名一致 |
| 项目特有条目 | `projects/<项目码>/项目特有规范.md` | 否 | 条目前缀须为 `STD-PRJ-<项目码大写>-` |
| 规范包 | `09_资产库/规范包/{stacks,domains}/*/PACK.md` | 是 | frontmatter 必填字段齐全 |
| 团队基线 | `<业务域>/standards/**/*.md` | 否 | 条目前缀须为 `STD-BASE-` |

## 产出契约

| 产出 | 路径 | 格式 |
|---|---|---|
| 生效规范快照（人读） | `.ai/spec-effective/<项目码>.md` | Markdown，分 A/B/C/D 四段 |
| 生效规范快照（机读） | `.ai/spec-effective/<项目码>.json` | JSON，含逐条来源链 |
| 执行日志 | `.ai/logs/spec-build.jsonl` | 追加一行 JSON |

## 执行方式

```bash
# 编译单个项目
python3 00_工作空间配置/skills/ai-spec-build/scripts/spec_build.py --project <项目码>

# 编译全部项目
python3 00_工作空间配置/skills/ai-spec-build/scripts/spec_build.py --all

# 只校验不写文件（CI 用）
python3 00_工作空间配置/skills/ai-spec-build/scripts/spec_build.py --all --check

# 列出全部包与版本
python3 00_工作空间配置/skills/ai-spec-build/scripts/spec_build.py --list
```

依赖：Python 3.8+ 与 PyYAML（`pip install pyyaml`）。

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

- **不修改任何规范内容。** 只读包与 manifest，只写 `.ai/spec-effective/` 与 `.ai/logs/`
- 不自动升级包版本。包升级必须由人改 manifest
- 不自动"修复"冲突。冲突一律以失败告终，裁决由人做
- 不检查条目正文的语义矛盾（无法机械判定），只处理显式声明的 `conflicts_with`
- 不调用模型

## 失败处理

| 失败情形 | 处理 |
|---|---|
| 校验失败 | 打印具体条目 ID、来源文件、失败原因，退出码 1，不写文件 |
| A 段超过 120 行预算 | 打印警告但**不失败**（提示有非硬约束条目被打成了 resident） |
| 项目特有条目超过 30 条 | 在快照 D 段标注警告，建议运行 `ai-spec-promote` |
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