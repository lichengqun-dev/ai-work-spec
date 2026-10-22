# SQL 方言规范 · db-dm8

> 本文件中的方言差异属于达梦 DM8 的通用特性，不绑定任何具体库表结构。

## STD-DM8-001 · CLOB 字段必须用 `DBMS_LOB.SUBSTR` 读取

**规则**：读取 CLOB 类型字段时，SQL 中必须用 `DBMS_LOB.SUBSTR(col, 长度, 起始位置)` 转换，不得直接 `SELECT col`。

**正例**：
```sql
SELECT DBMS_LOB.SUBSTR(property_value, 200, 1) AS V
FROM MYSCHEMA.some_table
WHERE id = '123';
```

**反例**：`SELECT property_value FROM …` —— 经 JDBC 返回的是 `dm.jdbc.driver.DmdbClob@…` 句柄，不是内容。

**原因**：达梦的 CLOB 是句柄引用，驱动不会自动物化。直接查会得到看似"有值"但不可用的句柄字符串，很容易被误判为数据异常，进而浪费时间排查一个不存在的脏数据问题。

---

## STD-DM8-002 · 空串与 NULL 不等价，断言前必须先验证

**规则**：达梦默认空串**不同于** NULL。写 `= ''` 或 `IS NULL` 之前，必须先查一次实际数据确认该字段的空值形态。

**正例**：先分别执行 `… WHERE col IS NULL` 与 `… WHERE col = ''` 各查一次，看清分布再写断言。

**反例**：按 MySQL 习惯直接写 `IS NULL` 或 `= ''`，假设二者等价。

**原因**：这是从 MySQL 迁移时最隐蔽的语义差异。断言写错**不会报错**，只会得到错误结论——在测试场景下意味着放过了真缺陷。

---

## STD-DM8-003 · 无表查询使用 `FROM DUAL`

**规则**：不依赖具体表的查询必须带 `FROM DUAL`。

**正例**：`SELECT 1 AS OK FROM DUAL`

**反例**：`SELECT 1`（MySQL 风格）

**原因**：用于连通性探测、时间获取、表达式验证。写成 MySQL 风格在部分客户端下能过、在另一些下报错，是不必要的环境相关故障源。

---

## STD-DM8-004 · 字符串拼接用 `||`，不用 `CONCAT`

**规则**：字符串拼接使用 `||` 运算符。`CONCAT` 在达梦中仅接受两个参数，多参拼接会报错。

**正例**：`SELECT a || '-' || b FROM t`

**反例**：`SELECT CONCAT(a, '-', b) FROM t`

**原因**：MySQL 的 `CONCAT` 支持任意参数个数，达梦不支持。多字段拼接是报表与导出 SQL 的常见写法，容易踩中。

---

## STD-DM8-005 · 表名、模式名、列名按大写查找

**规则**：通过 `ALL_TABLES` / `ALL_TAB_COLUMNS` 查元数据时，`OWNER` 与 `TABLE_NAME` 一般需要大写；比较条件用 `UPPER()` 包装。

**正例**：
```sql
SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS
WHERE OWNER = 'MYSCHEMA' AND TABLE_NAME = 'SOME_TABLE' ORDER BY COLUMN_ID;
```

**反例**：用全小写表名直接比较，返回空结果后误判为"表不存在"。

**原因**：达梦默认大小写敏感行为与 MySQL 的 `lower_case_table_names` 不同，用小写查询会**静默返回空集**——不是报错，是空集，更容易误导。

---

## STD-DM8-006 · 定位真实表名时必须排除备份表

**规则**：生产库中常存在大量历史备份表（`xxx_bak_yyMMdd`、`xxx-序号` 等）。按关键词找表后，必须优先选**无日期后缀、无连字符后缀**的正表；只有正表查不到时才逐个核对备份表。

**正例**：
```sql
SELECT TABLE_NAME FROM ALL_TABLES
WHERE OWNER = 'MYSCHEMA' AND UPPER(TABLE_NAME) LIKE '%ITEM%';
-- 选 ITEM_MAIN，而不是 ITEM_MAIN_BAK_250801
```

**反例**：`LIKE` 命中备份表后直接查它，得出"数据是空的"或"数据是脏的"的错误结论。

**原因**：备份表结构相似但数据是历史快照，查它得到的是过期结论。这是数据核对类任务最高频的误判来源。

---

> **本文件为 partial。** 分页写法统一约定、索引设计约定待补。