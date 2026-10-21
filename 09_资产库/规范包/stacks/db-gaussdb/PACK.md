---
pack: db-gaussdb
prefix: STD-GAUSS
dimension: db
key: db
version: 0.1.0
title: GaussDB / PostgreSQL 数据库
applies_when: 项目使用 GaussDB（PostgreSQL 协议兼容）或原生 PostgreSQL
owner: 待指定
updated: 2026-10-20
status: partial
files:
  - SQL 方言规范.md
---

# db-gaussdb

> **本包覆盖 GaussDB 与原生 PostgreSQL。** GaussDB 兼容 PostgreSQL 协议，
> 走 `org.postgresql.Driver`，所以在 SQL 方言层面两者可以共用一套约束。

## 这个包要解决什么

**AI 的默认 SQL 习惯来自 MySQL；而迁到达梦的团队手里又多了一套达梦习惯。
GaussDB/PostgreSQL 与这两者都不同，且差异方向经常相反。**

最典型的一条：达梦按**大写**查找标识符，PostgreSQL 默认折叠为**小写**——
从达梦迁过来的 SQL 在这里会报"表不存在"，而错误信息不会提大小写，只说你找的表没有。

同类的还有：达梦有 `DUAL`、PostgreSQL 没有；达梦的 `CONCAT` 只接受两个参数、
PostgreSQL 的是可变参数；达梦会把空串存成 NULL、PostgreSQL 会真实保留空串。

**套用任何一方的习惯都会写出能编译但语义错误、或直接报错的 SQL。**

## 与 `db-dm8` 的关系

两个包**互斥**（`db` 维度单选）。选了本包就不要选 `db-dm8`——达梦包里有多条规则
在 PostgreSQL 下是**反的**（大小写查找方向、空串/NULL、`FROM DUAL`、`DBMS_LOB`）。
同时引用会把两条相反的规则一起注入快照，而模型遇到冲突会静默挑一个。

## 条目文件

| 文件 | 内容 |
|---|---|
| [SQL 方言规范.md](./SQL%20方言规范.md) | 本包条目 |

## 待补充清单

- [ ] 索引与查询计划相关约定（GaussDB 分布式下的分布键选择）
- [ ] 分区表与大批量写入约定
- [ ] 事务隔离级别与锁行为差异
- [ ] JSON/JSONB 字段的使用约定
- [ ] 字符集与排序规则

> 条目按"真实批次反推"的顺序补充，不要一次性凭空写完。
> 本包当前的 7 条来自**一次真实项目的实测代码取证**（取证对象见 `SQL 方言规范.md` 的开头），不是推测。
> 取证来自哪个项目**不在本文件记录**——共享层不出现项目名，只承载通用的方言事实。