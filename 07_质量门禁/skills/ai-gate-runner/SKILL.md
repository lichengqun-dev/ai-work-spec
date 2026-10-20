---
name: ai-gate-runner
description: 执行质量门禁（六道：需求准入/原型确认/设计评审/代码评审/测试通过/归档交付）。进入下一阶段前、或用户要求跑门禁、签核、豁免时使用。
version: 1.0.0
stage: 07_质量门禁
owner: 待指定
updated: 2026-10-20
applicable_stacks: []
status: implemented
---

# 能力声明

统一的门禁执行器。读取 `07_质量门禁/gates/*.md` 的定义，执行其中标注 `auto:<检查项 ID>` 的检查项，
把结果写回批次状态文件。

**纯脚本，不调用模型。** 门禁结论必须可复现、可 diff、可审计——这些性质与"让模型判断一下"互斥。

## 输入契约

| 输入 | 来源 | 必需 | 校验规则 |
|---|---|---|---|
| 门禁定义 | `07_质量门禁/gates/gate-*.md` | 是 | 元信息含 `stage`/`blocking`/`auto_check`/`waivable`；检查项表格可解析 |
| 批次状态文件 | `.ai/state/<批次号>.yaml` | 是 | 含 `steps` 与 `artifacts`；`current_step` 必须在 `steps` 中 |
| 项目 manifest | `projects/<项目码>/project.yaml` | 是 | `repo` 字段指向项目文档仓或代码仓（未填则相关检查项记 skip） |
| 功能编号总表 | `.ai/index/功能编号总表.md` | 是 | 断链与覆盖率检查依赖它 |
| 上一道门禁状态 | 同一批次状态文件 | 是 | 必须为 `passed` / `waived`，否则拒绝执行 |

## 产出契约

| 产出 | 路径 | 格式 |
|---|---|---|
| 门禁结果 | 批次状态文件 `gates[]` | status / at / by / note / checks / manual_pending |
| 豁免记录 | 批次状态文件 `waivers[]` | gate / reason / approved_by / at / review_at |
| 执行日志 | `.ai/logs/<批次号>.jsonl` | 每次执行追加一行 JSON |

## 执行方式

```bash
S=07_质量门禁/skills/ai-gate-runner/scripts/gate_run.py

python3 $S --list-checks                                        # 检查项库与实现状态
python3 $S --project <码> --batch <批次号> --gate gate-03
python3 $S --project <码> --batch <批次号> --all                 # 按顺序跑到第一个未通过
python3 $S --project <码> --batch <批次号> --gate gate-03 --check
python3 $S --project <码> --batch <批次号> --gate gate-03 --confirm --by <名字>
python3 $S --project <码> --batch <批次号> --gate gate-03 --waive --by <名字> \
        --reason "<原因>" --expires YYYY-MM-DD
```

依赖：Python 3.8+ 与 PyYAML。退出码：`0` 通过 ｜ `1` 未通过或待人工确认 ｜ `2` 执行器自身错误。

## 前置条件（不满足则拒绝执行）

- 门禁定义文件可解析，且**每个 `auto:` 引用的检查项都已实现**——引用到未实现的检查项时，
  整道门禁拒绝执行，而不是跳过那一项
- 批次状态文件存在，`current_step` 在 `steps` 中
- **上一道门禁为 `passed` / `waived`**（门禁不允许跳步）
- `--confirm` / `--waive` 必须提供 `--by`；`--waive` 还必须提供 `--reason` 与 `--expires`
- 目标门禁的 `waivable` 不为 `no`

## 三条不能破的语义

**一、找不到检查项实现 → 整道门禁拒绝执行。**
静默跳过等于门禁失效，而失效的门禁比没有门禁更糟——它让人以为已经检查过了。

**二、`skip` 不等于 `pass`。**
缺少校验材料时记为 `skip`，转入人工确认，并说明"要做什么才能自动校验"。
把"没法校验"当成"校验通过"，是门禁最容易失效的方式。

**三、不代替人做判断。**
标注 `人` 的检查项原样列出等人工核对；门禁不会自动变成 `passed`，需要 `--confirm --by <名字>` 显式签核。
不是能力不足，而是**责任必须有人承担**。

**四、BLOCK 级 skip 不能用签核越过。**
签核的前提是「有人核对过了」；材料根本不存在时（无代码仓、无测试报告）无从核对。
这类项只能走 `--waive`（带批准人与复查期），不能走 `--confirm`。
否则门禁记录会显示「已通过」，而它其实什么都没查——这比没有门禁更糟。

## 边界（明确不做）

- **不自动修复。** 检查失败只报告，不改代码或文档——否则门禁会变成"自动掩盖问题的工具"
- 不代替人做 `人` 项的判断，只负责把清单摆出来
- 不自动豁免。豁免必须由人显式提供批准人与复查日期
- 不修改门禁定义文件
- 不调用模型

## 失败处理

| 失败情形 | 处理 |
|---|---|
| BLOCK 项 `fail` | 门禁置 `failed`，输出明细与定位，不可进入下一阶段 |
| WARN 项 `fail` | 记入待办，门禁可继续（状态为 `pending_manual`） |
| 存在 `人` 项或 `skip` 项 | 门禁置 `pending_manual`，输出人工清单与签核命令 |
| BLOCK 项 skip 且用户要求 `--confirm` | **拒绝签核**，说明需补齐材料或改用 `--waive`（状态保持 `pending_manual`） |
| 检查项抛异常 | 记为 `fail` 并附异常信息——**不允许把异常当成通过** |
| 门禁定义格式错误 | 退出码 2，拒绝执行（不跳过无法解析的检查项） |
| 上一道门禁未通过 | 退出码 2，提示先完成上一道 |

## 已知限制

- 3 个检查项固定返回 `skip`（静态检查、单元覆盖率、无代码仓时的密钥扫描），
  原因与补齐方式见 `references/检查项清单.md`
- `repo` 是兜底字段；文档仓 / 原型仓 / 代码仓分离时用 `docs_repo` / `prototype_repo` / `code_repo` 分别指定，
  否则原型覆盖率、密钥扫描、提交检查会互相污染（详见 `references/检查项清单.md`）
- `openapi-valid` 只做结构校验，完整规范校验建议在 CI 中追加 `@redocly/cli lint`
- `fn-coverage-design` 是"FN 出现在设计类产出物中"的**下限**检查；
  更严格的"每个 FN 有专属小节"由 `fn-design-section`（WARN）承担，分两级是为了避免误报阻断交付