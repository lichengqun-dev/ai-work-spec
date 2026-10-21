# 规范包索引

> 规范包 = L1 技术栈包 + L2 领域包。
> **项目不直接读包**，而是通过 `project.yaml` 组合、经 `ai-spec-build` 编译成生效快照。

## 1. 包清单

### L1 技术栈包（每维度单选，排他）

| 包 | 维度键 | 前缀 | 版本 | 状态 | 条目数 |
|---|---|---|---|---|---|
| [fe-vue2-elementui](./stacks/fe-vue2-elementui/PACK.md) | `fe` | `STD-VUE2-` | 0.1.0 | 🚧 骨架 | 4 |
| [fe-vue3-elementplus](./stacks/fe-vue3-elementplus/PACK.md) | `fe` | `STD-VUE3-` | 0.1.0 | ⚠️ 部分 | 5 |
| [fe-react-antd](./stacks/fe-react-antd/PACK.md) | `fe` | `STD-REACT-` | 0.1.0 | 🚧 骨架 | 4 |
| [be-springboot2-java8](./stacks/be-springboot2-java8/PACK.md) | `be` | `STD-SB2-` | 0.1.0 | ⚠️ 部分 | 5 |
| [be-springboot3-java17](./stacks/be-springboot3-java17/PACK.md) | `be` | `STD-SB3-` | 0.1.0 | ⚠️ 部分 | 5 |
| [db-dm8](./stacks/db-dm8/PACK.md) | `db` | `STD-DM8-` | 0.1.0 | ⚠️ 部分 | 6 |
| [db-gaussdb](./stacks/db-gaussdb/PACK.md) | `db` | `STD-GAUSS-` | 0.1.0 | ⚠️ 部分 | 7 |

> 上表是**示例包**，演示规范包长什么样。套用到其他团队时按自己的技术栈增删——
> 包不是预置越多越好，按需建（见第 6 节）。

**`db` 维度有两个包，且它们互斥**——`db-dm8`（达梦）与 `db-gaussdb`（GaussDB / PostgreSQL）。
选错不只是"少了几条约束"：两个包里有多条规则**方向相反**
（大小写查找、空串与 NULL、`FROM DUAL`、`CONCAT` 参数个数），同时选中会把相反的规则一起注入快照，
而模型遇到冲突会静默挑一个。**manifest 里 `db` 只能选一个。**

### L2 领域包（多选叠加，需在 manifest 声明优先级）

> 领域包由使用方按自己的业务领域新建，本仓库只提供结构与两个空骨架示例。

| 包 | 前缀 | 版本 | 状态 | 条目数 |
|---|---|---|---|---|
| [platform-base](./domains/platform-base/PACK.md) | `STD-DOM-PLAT-` | 0.1.0 | 🚧 骨架 | 0 |
| [info-security](./domains/info-security/PACK.md) | `STD-DOM-INFOSEC-` | 0.0.1 | 🚧 骨架 | 0 |

**本仓库不预置任何领域的业务约束。** 领域包的内容是各团队自己的业务知识，本仓库只提供结构与机制——领域包由使用方按自己的业务领域新建。

上表两个包是空骨架示例，说明领域包长什么样。空包是合法状态（`files: []`）。**不要为了"看起来完整"而凭空写业务约束**——写错的信息安全约束比没有约束更糟，它会让团队以为已经合规。

## 2. 为什么这样切分

**按单一技术组件切分，不按技术栈组合切分。** 后者会组合爆炸：3 个前端 × 2 个后端 × 1 个数据库 = 6 个包，
且"接口必须定义错误码"这类跨栈规范要改 6 次。按组件切分后，组合由项目 manifest 负责。

**技术栈包排他，领域包叠加。** 一个项目不可能同时用 Vue 2 和 Vue 3 做同一个前端，所以同维度天然不冲突，合并逻辑极简；但一个项目可能同时属于多个业务领域，多选必然冲突，因此需要在 manifest 里显式声明优先级。

## 3. 包目录结构

```
stacks/fe-vue3-elementplus/
├── PACK.md              ← 包元信息（YAML frontmatter，机读）+ 包说明（人读）
├── 编码规范.md           ← 条目文件
└── 状态管理规范.md
```

`PACK.md` 的 frontmatter 是**机读的**，`ai-spec-build` 靠它定位包与条目文件：

```yaml
---
pack: fe-vue3-elementplus   # 包 id，manifest 中引用
prefix: STD-VUE3            # 该包条目的编号前缀，构建时校验
dimension: fe               # 维度键
key: fe                     # 对应 manifest 中 stacks 的键
version: 0.1.0              # 语义化版本
title: Vue 3 + Element Plus 前端栈
applies_when: 项目前端使用 Vue 3.x + Element Plus + Vite
owner: 待指定
updated: 2026-10-19
status: partial             # skeleton | partial | stable
files:                      # 条目文件清单，按顺序解析（可为空列表）
  - 编码规范.md
---
```

## 4. 条目格式（必须严格遵守）

条目是人机共读的 Markdown，元信息放在紧随标题的 HTML 注释里——既保持可读性，又能被脚本稳定解析。

````markdown
## STD-VUE3-001 · 组件统一使用 `<script setup>` + TypeScript

<!-- meta
tier: resident
scope: 组件写法
frozen: false
-->

**规则**：所有 `.vue` 组件使用 `<script setup lang="ts">`，不使用 `export default`。

**正例**：
```vue
<script setup lang="ts">
const props = defineProps<{ id: string }>()
</script>
```

**反例**：使用 Options API，或在 `<script setup>` 里写 `export default`。

**原因**：……

**例外**：迁移中的老页面允许保留 Options API。
````

### 字段说明

| 字段 | 取值 | 作用 |
|---|---|---|
| `tier` | `resident` / `indexed` | `resident` 进快照 A 段（常驻注入，≤120 行）；`indexed` 进 B 段索引 |
| `scope` | 自由文本 | 按需检索的触发场景（如"编写 Service 层时"） |
| `frozen` | `true` / `false` | `true` 表示项目层不可覆盖/禁用，构建会拒绝；只能走知识库 Owner 流程 |
| `conflicts_with` | 条目 ID 列表（逗号分隔） | 声明与另一条目语义冲突。跨层自动裁决；同层必须由 manifest 的 `domains` 顺序裁决，否则构建失败 |

**`tier` 取值纪律**：`resident` 是稀缺资源。判据是"**不看这条会不会做错**"，不是"这条重不重要"。一个包内 `resident` 通常不超过 3 条。

**`conflicts_with` 的用法**：只在两条规则对**同一个决策点给出不同答案**时使用。例如领域包 A 说"金额用 DECIMAL 存两位小数"、领域包 B 说"金额用 BIGINT 存分"——这是真冲突，必须声明。而"表单用自研组件"和"表格用虚拟滚动"不是冲突，只是不同主题。

### 条目编号

见 `../../../00_工作空间配置/命名与编号规范.md` 第 5 节。编号在包内**顺序分配、永不复用**；删除条目时保留编号并标记 `[已废弃]`，不回收。

## 5. 构建时校验（由 `ai-spec-build` 执行，不通过即失败）

1. `PACK.md` frontmatter 必填字段齐全，`files` 列出的文件都存在。
2. 条目前缀与所在包的 `prefix` 一致。
3. 条目编号在全库范围内唯一（跨包重复即错误）。
4. manifest 引用的包与版本存在且匹配（版本锁定，升级需显式改 manifest）。
5. `overrides` 引用的条目存在；对 `frozen` 条目的覆盖/禁用直接拒绝。
6. `disable` 必须带 `expires`；禁用基线/包条目还需 `approved_by`。
7. 同层冲突无优先级声明 → 失败。

## 6. 包的生命周期

| 状态 | 含义 |
|---|---|
| 🚧 `skeleton` | 只有 PACK.md 与文件骨架，条目待填 |
| ⚠️ `partial` | 部分条目已填充，可支撑实际开发但有明显空缺 |
| ✅ `stable` | 条目完整，经过 ≥1 个真实批次验证 |

**填充顺序：按需建包，不要一次性建全。** 先填试点项目实际用到的那几个包，用真实批次反推条目，而不是坐在会议室里凭空写通用条目——后者实战中往往一条都用不上，然后被整体废弃。
