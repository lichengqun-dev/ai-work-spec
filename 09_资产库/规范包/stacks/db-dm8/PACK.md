---
pack: db-dm8
prefix: STD-DM8
dimension: db
key: db
version: 0.1.0
title: 达梦 DM8 数据库
applies_when: 项目使用达梦 DM8
owner: 待指定
updated: 2026-10-19
status: partial
files:
  - SQL 方言规范.md
---

# db-dm8

## 实测技术栈

| 组件 | 版本 |
|---|---|
| 默认端口 | 5236 |
| JDBC URL | jdbc:dm://host:5236/dbname |
| 驱动 | dm.jdbc.driver.DmDriver |

## 这个包要解决什么

**本 workspace 全部项目使用达梦 DM8，不是 MySQL。** 任何涉及 SQL 的生成、评审与测试，以本包为准。

AI 的默认 SQL 习惯来自 MySQL / PostgreSQL，而达梦在以下几个点有实质差异，**套用 MySQL 习惯会写出能编译但语义错误的 SQL**：

- CLOB 字段经 JDBC 读取返回的是句柄对象而非字符串
- 空串与 NULL 不等价
- 表名、模式名、列名的大小写敏感行为不同
- `CONCAT` 只接受两个参数

## 条目文件

| 文件 | 内容 |
|---|---|
| [SQL 方言规范.md](./SQL 方言规范.md) | 本包条目 |

## 待补充清单

- [ ] 分页写法的统一约定（ROWNUM vs LIMIT）
- [ ] 索引设计与命名约定
- [ ] DDL 变更与回滚流程
- [ ] 字符集与排序规则
- [ ] 与 ORM 框架的兼容注意事项

> 条目按"真实批次反推"的顺序补充，不要一次性凭空写完。
