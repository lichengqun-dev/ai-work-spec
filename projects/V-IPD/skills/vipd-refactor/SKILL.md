---
name: vipd-refactor
description: V-IPD 重构操作 Skill。按 spec/constraints/standards/guides 四层文档执行。在写任何代码前，先读取对应层的规范。
---

# V-IPD 重构操作 Skill

## 执行顺序

写任何代码前，按以下顺序读取规范：

```
1. docs/spec/tech-stack.md           → 用什么技术
2. docs/constraints/tech-constraints.md → 什么不能用
3. docs/standards/coding-standard.md   → 代码怎么写
4. docs/spec/functional-scope.md       → 做什么功能
5. docs/guides/page-replication.md    → 前端页面怎么复刻
6. docs/guides/vendor-replacement.md  → 供应商包怎么替换
7. docs/guides/lowcode-to-hardcode.md → 低码页面怎么转硬编码
```

## 快速检查（每次提交前）

```bash
# 1. 无供应商依赖
grep -r "com.ak.iform\|com.aoborsoft\|com.baomidou" */pom.xml
# 期望：空

# 2. 无供应商包名 import
grep -rn "import com.ak.iform\|import com.aoborsoft\|import com.baomidou" */src/
# 期望：空

# 3. 包名全在新命名空间
find */src -name "*.java" | xargs grep -L "package cn.voyah.vipd"
# 期望：空（vipd-legacy 除外）

# 4. 每个服务只有一个启动类
find */src -name "*Application.java" | sort
# 期望：每模块恰好 1 个

# 5. 数据库字段无尾下划线
grep -rn "create_by_\|update_by_\|deleted_" */src/main/resources/mapper/*.xml
# 期望：空

# 6. 逻辑删除用 is_deleted 0/1
grep -rn "deleted_.*=.*'N'" */src/
# 期望：空
```

## 文档层级说明

| 层 | 回答什么 | 变更流程 |
|---|---|---|
| `spec/` | 是什么 | 架构评审 |
| `constraints/` | 不能做什么 | 不可变更（除非用户明确要求） |
| `standards/` | 怎么写 | 技术评审 |
| `guides/` | 怎么做某件事 | 团队协商 |
