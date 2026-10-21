---
name: ai-spec-build
description: 把多层规范（基线/技术栈包/领域包/项目层）编译成单一生效快照。当接入新项目、改了规范包或 manifest、或需要确认某个项目该遵守哪些规范时使用。
---

# ai-spec-build

> 本文件由 `00_工作空间配置/scripts/build_claude_skills.py` **生成**，不要手改。
> 要改这个 Skill，改它的真实定义后重跑该脚本。

完整定义在知识库中（`00_工作空间配置/skills/ai-spec-build`）：

| 内容 | 文件 |
|---|---|
| 契约与前置条件 | `00_工作空间配置/skills/ai-spec-build/SKILL.md` |
| **执行指令** | `00_工作空间配置/skills/ai-spec-build/prompt.md` |
| 知识索引 | `00_工作空间配置/skills/ai-spec-build/references/INDEX.md` |

## 执行方式

1. 读 `00_工作空间配置/skills/ai-spec-build/SKILL.md`，**逐条核对「前置条件」**——不满足就停下并说明是哪一条不满足，
   不要"先跑跑看"
2. 读 `00_工作空间配置/skills/ai-spec-build/prompt.md`，**按它执行**。它是这个 Skill 的指令本体
3. `references/` 默认只加载 `INDEX.md`，按它的「何时读取」列按需读取，单次不超过 3 个文件
4. 产出物按 `SKILL.md` 的产出契约落位，并登记到批次状态文件 `projects/<项目码>/.agent/state/<批次号>.yaml` 的 `artifacts`

## 为什么要经过这一层

这层是**指针**：真实定义只有一份（在上面的路径里），这里是给 Claude 的 skill 发现机制看的入口。
把内容复制到这里会产生需要同步的副本，而副本一定会分叉——
所以本文件是生成的，`--check` 模式可以验证它是否与真实定义一致。
