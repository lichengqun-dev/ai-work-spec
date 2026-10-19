# 迭代开发

> 影响面分析 → 增量设计 → 变更控制 → 发布说明。**P2 阶段交付。**

迭代与新建的**本质区别不是步骤少，而是存在基线**。所以核心 Skill 不是「生成」，而是「对比」。

## 本域的 Skill

| Skill | 职责 | 说明 |
|---|---|---|
| [ai-iteration-01-impact](./skills/ai-iteration-01-impact/SKILL.md) | 变更影响面分析 | 输入一个新需求，输出：受影响的 FN、接口、数据表、测试用例范围、工作量等级。 |
| [ai-iteration-02-delta-spec](./skills/ai-iteration-02-delta-spec/SKILL.md) | 增量设计 | 只写差异，不重写文档。产出是变更说明而非完整设计。 |
| [ai-iteration-03-change-control](./skills/ai-iteration-03-change-control/SKILL.md) | 变更登记与基线对比 | 登记变更、与原基线对比、开变更子批次。 |
| [ai-iteration-04-release](./skills/ai-iteration-04-release/SKILL.md) | 发布说明与版本对齐 | 生成发布说明、版本号对齐、上线步骤。 |

## 依赖关系

| 上游 | 已有系统的基线（历史批次产出物） |
| 下游 | 回到 `03`/`04` 域做增量实现与回归 |
| 资产 | `.ai/index/依赖关系图.md` |

## 本域的规范

| 变更管理规范 | `standards/变更管理规范.md` |

## 状态

**P2 阶段交付。** 本域 Skill 目前均为占位实现——`SKILL.md` 已定义职责与边界，
但收到调用请求时会因前置条件（"未实现"）而拒绝执行。

**请勿在实现前调用。** 占位 `SKILL.md` 的作用是让编排层能正确判断"这个 Skill 还不能用"，
而不是让它看起来可用。
