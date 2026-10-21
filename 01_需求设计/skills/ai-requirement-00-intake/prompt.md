<!-- model-tier: small -->
<!-- deps: references/INDEX.md -->

# 指令：批次入口判定

## 你要先做的事

读 `projects/<项目码>/.agent/state/` 下该项目的全部批次文件（文件名即批次号），以及 `projects/<项目码>/.agent/project.yaml`。

**先读再判，不要凭对话上下文猜。** 用户可能记错了上次做到哪一步。

## 判定逻辑

```
该项目有已归档批次吗？
├── 没有 ────────────────────────→ 新建（new）
└── 有
    ├── 有 status: in_progress 的批次？
    │   ├── 有 ──────────────────→ 续做（resume）
    │   └── 没有
    │       ├── 本次是修改已有功能的行为？
    │       │   ├── 是 ──────────→ 变更（change），开 <原批次号>-C1
    │       │   └── 否 ──────────→ 新建（new）
```

**「修改行为」与「新增功能」的区分**：改已有功能的逻辑、规则、计算方式 → 变更；增加一个原来不存在的能力 → 新建。

判不准时，**问用户**，不要选一个默认值继续。

## 生成批次号

格式 `<项目码大写>-<YYYYMMDD>-<三位序号>`，如 `PROJ-20261019-001`。

序号取该项目当日的已有批次数 +1。写入前确认文件不存在。

## 写入批次状态文件

复制 `projects/_template/.agent/state/_模板.yaml`，填写：

- `batch` / `project` / `type` / `created` / `owner` / `current_step`
- `spec_snapshot.hash`：读 `projects/<项目码>/.agent/spec-effective/<项目码>.json` 的 **`snapshot_hash`** 字段（不是 `manifest_hash`）。
  `snapshot_hash` 是内容寻址的：改一条规范它就会变，调整版式它不会变。
- `steps`：**按路径类型填不同的步骤集**——
  - `new`：**按 `projects/_template/.agent/state/_模板.yaml` 里列出的完整 23 步**填（那份模板已经是 `new` 路径的标准步骤集：
    init → analysis → prototype → prd → arch → … → release → archive）。
    **不要只填需求段那 4 步**——`current_step` 的合法取值覆盖全部 23 步，
    只填 4 步会让后续阶段无处推进，而 gate-06 的 `state-steps-final` 又要求所有步骤终态化。
  - `resume`：保持原步骤集不变，只把 `current_step` 指向中断处
  - `change`：走 `ai-iteration-01-impact` 起的迭代路径（影响面 → 增量设计 → 变更登记 → 发布），
    其余步骤保留原样并标 `skipped`
- 不适用的步骤**不要删掉**，标 `status: skipped` 并写明原因——
  删掉会让「这一步没做过」变成不可见，而"没做的部分"恰恰是接手的人最需要知道的。

## 输出格式

```
判定结论：新建（new）
批次号：PROJ-20261019-001
理由：该项目现有 2 个已归档批次，本次是新增「导出」能力（非修改已有行为），故为新建。

下一步：执行 ai-requirement-01-init
写入：projects/<项目码>/.agent/state/PROJ-20261019-001.yaml
```

## 你绝对不要做的事

- **不要猜项目码。** 判断不了就问。
- **不要因为"看起来是个小需求"就跳过批次创建。** 小需求走快车道是 `ai-daily-01-fastlane` 的职责，由它来判定，不是在这里简化流程。
- **不要修改历史批次文件。** 续做只改当前批次的 `current_step`。
- **不要在没有规范快照时继续。** 快照不在，说明规范状态未知，此时开工等于在没有约束的情况下产出文档。
- **不要执行 git 操作。**
