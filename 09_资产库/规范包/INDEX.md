# 规范包索引

> 规范包 = 技术栈包 + 领域包，是**域级公共资产**。
> **项目通过 `project.yaml` 声明用了哪些包；包内规范不编译进快照**——
> 到对应阶段按各域 `README.md` 的「本阶段约束」表读取**原文**（见 `../../../00_工作空间配置/上下文注入规范.md`）。
> 快照里只留一张指针表（哪个维度选了哪个包），回答"该去读哪一份原文"。

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
├── 编码规范.md           ← 规范原文（阶段加载时整份读）
└── 状态管理规范.md
```

`PACK.md` 的 frontmatter 是**机读的**，`ai-spec-build` 靠它定位包与**阶段加载时要读的原文文件**：

```yaml
---
pack: fe-vue3-elementplus   # 包 id，manifest 中引用
prefix: STD-VUE3            # 该包规范文件的段落锚点前缀（供引用定位）
dimension: fe               # 维度键
key: fe                     # 对应 manifest 中 stacks 的键
version: 0.1.0              # 语义化版本
title: Vue 3 + Element Plus 前端栈
applies_when: 项目前端使用 Vue 3.x + Element Plus + Vite
owner: 待指定
updated: 2026-10-19
status: partial             # skeleton | partial | stable
files:                      # 规范原文清单（阶段加载时按需读取；可为空列表）
  - 编码规范.md
---
```

## 4. 规范文件的写法

包内规范文件是**给人读的原文**——到对应阶段整份读取，不切条、不摘要、不改写。
文件里用 `## STD-<包前缀>-NNN · 标题` 作**段落锚点**，方便引用与定位
（门禁会写「符合 `STD-BASE-311`」，Skill 会写「见 `STD-GAUSS-005`」，都指得到它）。

````markdown
## STD-VUE3-001 · 组件统一使用 `<script setup>` + TypeScript

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

**不写 `<!-- meta -->` 块。** 早先条目带 `tier` / `scope` / `frozen` / `conflicts_with` 四个机器字段，
那是"条目要进快照"时代的产物——`tier` 决定进 A 段还是 B 段、`scope` 进 B 段的触发场景列、
`frozen` 表示项目层不得覆盖。快照现在只装项目级内容，这四个字段的机器语义**全部消失**。

| 退役字段 | 现在怎么办 |
|---|---|
| `tier` | 域级不进快照，没有常驻/按需之分，删 |
| `scope` | 域级是「整份读原文」，条目级适用范围不再参与机器判断，删 |
| `frozen` | **没有覆盖机制了，拦截无从谈起**。「这条不可协商」用正文里的一行文字表达 |
| `conflicts_with` | 同上。两个包对同一决策点给不同答案是**内容问题**，交给评审而不是构建期仲裁 |

**锚点编号纪律**（不变）：编号在包内**顺序分配、永不复用**；删除条目时保留编号并标记 `[已废弃]`；
编号一经启用，改正文可以，**改编号等于断掉所有引用**。编号规则见
`../../../00_工作空间配置/命名与编号规范.md` 第 5 节。

## 5. 构建时校验（由 `ai-spec-build` 执行，不通过即失败）

1. `PACK.md` frontmatter 必填字段齐全，`files` 列出的文件**都存在**——
   路径写错会让人在对应阶段找不到规范，而那时已经离错误现场很远。
2. manifest 引用的包存在，且**版本与锁定的版本一致**（包升级不会自动影响项目，升级要显式改 manifest）。
3. manifest 中 `stacks` 的键与该包的 `key` 一致（`db` 维度选错包会注入方向相反的规则）。
4. 项目级条目前缀正确、编号在项目内唯一。

**包内条目不再参与构建校验**——它们不进快照。编号唯一性与引用有效性由
`ai-spec-check` 的悬空引用检查兜底，语义矛盾交给评审。

## 6. 包的生命周期

| 状态 | 含义 |
|---|---|
| 🚧 `skeleton` | 只有 PACK.md 与文件骨架，条目待填 |
| ⚠️ `partial` | 部分条目已填充，可支撑实际开发但有明显空缺 |
| ✅ `stable` | 条目完整，经过 ≥1 个真实批次验证 |

**填充顺序：按需建包，不要一次性建全。** 先填试点项目实际用到的那几个包，用真实批次反推条目，而不是坐在会议室里凭空写通用条目——后者实战中往往一条都用不上，然后被整体废弃。
