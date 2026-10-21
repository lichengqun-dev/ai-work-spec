---
name: ai-design-05-frontend-spec
description: 产出前端设计：页面清单、组件拆分、状态归属、接口调用映射。接口契约之后使用。
---

# ai-design-05-frontend-spec

> 本文件由 `00_工作空间配置/scripts/build_claude_skills.py` **生成**，不要手改。
> 要改这个 Skill，改它的真实定义后重跑该脚本。

完整定义在知识库中（`02_概要详细设计/skills/ai-design-05-frontend-spec`）：

| 内容 | 文件 |
|---|---|
| 契约与前置条件 | `02_概要详细设计/skills/ai-design-05-frontend-spec/SKILL.md` |
| **执行指令** | `02_概要详细设计/skills/ai-design-05-frontend-spec/prompt.md` |
| 知识索引 | `02_概要详细设计/skills/ai-design-05-frontend-spec/references/INDEX.md` |

## 执行方式

1. 读 `02_概要详细设计/skills/ai-design-05-frontend-spec/SKILL.md`，**逐条核对「前置条件」**——不满足就停下并说明是哪一条不满足，
   不要"先跑跑看"
2. 读 `02_概要详细设计/skills/ai-design-05-frontend-spec/prompt.md`，**按它执行**。它是这个 Skill 的指令本体
3. `references/` 默认只加载 `INDEX.md`，按它的「何时读取」列按需读取，单次不超过 3 个文件
4. 产出物按 `SKILL.md` 的产出契约落位，并登记到批次状态文件 `projects/<项目码>/.agent/state/<批次号>.yaml` 的 `artifacts`

## 为什么要经过这一层

这层是**指针**：真实定义只有一份（在上面的路径里），这里是给 Claude 的 skill 发现机制看的入口。
把内容复制到这里会产生需要同步的副本，而副本一定会分叉——
所以本文件是生成的，`--check` 模式可以验证它是否与真实定义一致。
