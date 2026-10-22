# SQL 方言规范 · db-gaussdb

> 本文件中的方言差异属于 GaussDB / PostgreSQL 的通用特性，不绑定任何具体库表结构。
>
> **这些条目不是从文档抄的，是从真实项目的代码里取证的**——
> 取证对象：一个使用 GaussDB 的后端工程的**全部 `*.sql`、Mapper XML 与数据源配置**。
>
> 取证样本的**具体项目不在此记录**：本文件属于共享层，只承载"换成另一个团队也成立"的方言事实。
> 需要追溯某一条是从哪段代码来的，看该项目的项目级文档（带编号条目）与其批次产出物——
> 项目相关信息一律只在 `projects/<项目码>/` 下。

## STD-GAUSS-001 · 标识符默认折叠为小写，不要指望大写查找

**规则**：PostgreSQL 会把**未加引号**的标识符折叠为小写。写表名、列名一律用小写蛇形，不要加双引号。

**正例**：`SELECT * FROM biz_order_relation WHERE order_no = ?`

**反例**：`SELECT * FROM "BIZ_ORDER_RELATION"` —— 报 `relation does not exist`。

**原因**：**这条与达梦的方向正好相反。** 达梦按大写查找，PostgreSQL 默认按小写。
从达梦迁过来的 SQL 在这里会失败，而错误信息只说"表不存在"，**不会提示是大小写问题**——
于是排查方向会被带到"表被删了"或"连错库了"上去。

元数据查询同理：`information_schema.columns` 里的 `table_name` 是小写，
用大写去比较会**静默返回空集**（不是报错，是空集，更容易误判为"表不存在"）。

---

## STD-GAUSS-002 · 空串是真实值，不等于 NULL

**规则**：`''` 与 `NULL` 是两个不同的值，必须分别判断。涉及可空字段的校验，`IS NULL` 与 `= ''` 都要写。

**正例**：先分别查一次，看清分布再写断言：
```sql
SELECT count(*) FROM biz_order WHERE order_no IS NULL;   -- 真无常
SELECT count(*) FROM biz_order WHERE order_no = '';      -- 空串
```

**反例**：只写 `WHERE col IS NULL` 就认为覆盖了"没有值"的情形。

**原因**：**达梦（和 Oracle）会把空串存成 NULL，PostgreSQL 会真实保留 `''`。**
从达梦迁过来的等价判断会**漏掉空串行**——不报错，只是少查了数据，结论悄悄偏掉。

反向也成立：在达梦上"空串即 NULL"，迁到 PostgreSQL 后同一列会同时出现 `NULL` 和 `''` 两种"空"，
只判一种就会漏。这是**数据校验类任务最高频的静默错误来源**。

---

## STD-GAUSS-003 · 没有 `DUAL`，无表查询直接 `SELECT`

**规则**：不依赖具体表的查询直接写 `SELECT <表达式>`，**不要** `FROM DUAL`。

**正例**：`SELECT 1 AS ok`

**反例**：`SELECT 1 FROM DUAL` —— 报 `relation "dual" does not exist`

**原因**：达梦/Oracle 需要 `FROM DUAL`，PostgreSQL 没有这个伪表。
用于连通性探测、取当前时间、验证表达式时容易踩中；而报错信息会让人以为是建表脚本漏了。

---

## STD-GAUSS-004 · 分页用 `LIMIT` / `OFFSET`，没有 `ROWNUM`

**规则**：分页写 `... ORDER BY <唯一键> LIMIT n OFFSET m`。不要用 `ROWNUM`，也不要依赖"无序分页"。

**正例**：`... WHERE is_deleted = 1 ORDER BY id DESC LIMIT 20 OFFSET 40`

**反例**：`... WHERE ROWNUM <= 20`（达梦/Oracle 写法，PostgreSQL 无 `ROWNUM` 伪列）

**原因**：达梦用 `ROWNUM`、MySQL 用 `LIMIT`，PostgreSQL 是 `LIMIT`/`OFFSET`。
**另外**：`OFFSET` 分页在**不指定 `ORDER BY`** 时结果不稳定——数据库不保证返回顺序，
翻页会重复或漏行。`ORDER BY` 后要跟唯一键，不能只按可重复的列（如状态、日期）排。

---

## STD-GAUSS-005 · `concat()` 与 `||` 对 NULL 的处理不同，可空字段上要选对

**规则**：`concat()` 接受任意个参数且**把 NULL 当空串**；`||` 只要有一个操作数是 NULL，
**整个结果就是 NULL**。拼接可空字段时必须明确选哪一个。

**正例**（模糊搜索，任一参数为空也不该丢行）：
```sql
AND order_no LIKE CONCAT('%', #{orderNo}, '%')
```

**反例**：`AND (a || '-' || b) LIKE ?` —— 当 `a` 或 `b` 为 NULL 时整个表达式为 NULL，
条件恒不成立，**匹配行被静默丢掉**，看起来像"没数据"。

**原因**：达梦的 `CONCAT` 只接受**两个**参数，所以从达梦迁过来的代码往往绕开它去用 `||`，
到了 PostgreSQL 就带着 NULL 语义的坑。反过来，从 MySQL 迁过来的人习惯 `CONCAT`，
三参以上没问题，但不知道 `||` 与它不等价。

**这条是本包里最隐蔽的一条**：错误不报错、不返回空集，只是少几行。

---

## STD-GAUSS-006 · 跨 schema 必须显式限定，不要依赖 `search_path`

**规则**：引用默认 schema 之外的对象时，一律写全 `<schema>.<object>`。
不要因为"当前连接配了 `currentSchema`"就省略。

**正例**：`SELECT ... FROM public.biz_part_role_scope`

**反例**：同一段 SQL 在 A 环境（`search_path=public`）能跑，在 B 环境（未设）报"表不存在"。

**原因**：`search_path` 来自连接参数或数据源配置（如 JDBC URL 上的 `currentSchema=public`），
**同一份 SQL 在不同环境解析到不同 schema**。这类问题只在特定环境复现，
本地测不出来——而 DDL 里显式写全限定名是零成本的。

---

## STD-GAUSS-007 · 字段注释用独立的 `COMMENT ON` 语句

**规则**：PostgreSQL 不支持 `CREATE TABLE` 里的内联 `COMMENT`。字段说明必须写成独立的
`COMMENT ON COLUMN <schema>.<table>.<column> IS '…'`。

**正例**：
```sql
create table public.biz_order_relation (
    id bigint not null primary key,
    order_no varchar(50) not null
);
comment on table public.biz_order_relation is '业务单据与流程实例关联表';
comment on column public.biz_order_relation.order_no is '业务编号';
```

**反例**：`order_no varchar(50) COMMENT '业务编号'`（MySQL 写法，PostgreSQL 直接语法错误）

**原因**：**门禁的 `db-field-comments` 检查项会校验这一点**——它接受 `COMMENT` 或
`COMMENT ON COLUMN`，而只有后者在这里能真正执行。注释写全，
`COMMENT ON TABLE` 的目标名**必须与建表名逐字一致**（含前缀），否则语句会失败。

---

> **本文件为 partial（7 条）。** 索引与分布键、分区与批量写入、隔离级别与锁、JSONB 使用、
> 排序规则待补——这些要等真实批次里踩到再写，凭空写的条目实战中往往一条都用不上。