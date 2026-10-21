---
owner: dev
title: 新人第一次用 AI 做 V-IPD 全栈 · 注意事项
last_modified: 2026-10-09
---

# 新人第一次用 AI 做 V-IPD 全栈 · 注意事项

> **给谁看：** 第一次在 V-IPD 项目里用 AI 同时改前端和后端的人。
> **这篇不讲业务表、业务口径**（那些在《核心业务模型》《数据库设计规范》里），只讲：**进场前要先知道什么、AI 说的话怎么验证、两代后端怎么不踩坑。**
> 例子来自本项目实测（本地启动 12 服务、dev 库对账、验收评审）。

相关材料：`./skills/run-powerproject-backend/SKILL.md`（本地启动）；本知识库根 `CLAUDE.md`（知识库规则）。

---

## 一、进场前必须说清楚的点

### 1.1 你在改三个仓，不是一个项目

| 仓 | 干什么 | 技术栈 |
|----|--------|--------|
| `powerprojectforjava-backend` | 一期后端（iform 重框架，5 服务） | JDK 8 + Spring Boot 2.3 + Netflix |
| `pp-powerproject-extend` | 二期后端（轻服务群，7 服务） | JDK 8 + Spring Boot 2.6 + MyBatis-Plus |
| `powerprojectforjava-frontend` | 前端（多入口） | Vue 2.6 + Vue CLI 5 |

前端 `npm run dev` 打开页面**不等于**你本机起了后端。接口打到哪，看 `vue.config.js` 的 proxy：匹配本地端口走本地 Java，兜底走 `core-test.voyah.cn`（环境上的旧代码）。

### 1.2 两代后端，规矩完全不同

| 维度 | 一期 | 二期 |
|------|------|------|
| 业务表单 | iform 动态表单引擎 + BO 定义 + Activiti（很多页面不是硬编码） | 硬编码 Controller/Service/Mapper |
| 表前缀 | `pp_*` / `iform_*` / `act_*` | `extends_*` |
| 字段风格 | 带下划线后缀 `id_`/`create_by_` | 无后缀 `id`/`create_user_id` |
| 逻辑删除 | `deleted_='N'/'Y'` | `is_delete=1`（1=正常！） |
| 改代码落点 | 只改 `pp-project-root`/`pp-document-root`，**iform-* 会被上游 SVN 同步覆盖** | 对应 `pp-*-root`，随便改 |
| 调平台能力 | 本仓内部 Feign | 只走 `iform-integration-layer` 的 SDK |
| 启动时间 | 3~9 分钟 | ~2 分钟 |

**AI 最容易犯的错**：在一期模块里写二期风格的字段名（或反过来）。让它先 `describe` 表再写代码。

### 1.3 连数据库：全栈 AI 的基础设施

没有库，AI 只能猜表名、猜字段、猜关联。猜错的关联，代码能编译、页面能出数，但数是错的。

进场清单：

| 准备 | 说明 |
|------|------|
| Python + psycopg2 | GaussDB 是 PG 协议兼容，直接连 |
| 测试库 | `10.82.45.158:8000` / `PowerProject6_20260512` / `pp` / `<见密码保险柜>` |
| 预发布库 | `10.82.45.6:8000` / `PowerProject6` / `root` / `<见密码保险柜>` |
| GaussDB 保留字 | `id`/`status`/`location`/`user`/`group` 查询加双引号 |
| 只读习惯 | 对账用 SELECT；写测试数据前先想清理 |
| 逻辑删除值域 | 一期 `'N'`；二期 `1`（1=正常，0/2=删除，**与常见约定相反**） |

**硬规矩：** AI 声称"表里有某某字段/有某某外键"时，必须让它 `describe` 或跑一条 `SELECT`。没查库的结论当没说过。

### 1.4 真实配置不在 Git 里

| 你以为 | 实际 |
|--------|------|
| 数据库、Redis、Nacos 地址在 yml 里 | 一期走 XML 多级数据源加载（`conf/dataSource-postgres-local.xml`）；二期 yml 直配但真实值在 Nacos |
| 改完 yml 本地就生效 | **必须同步复制到 `target/classes`**（jar 是旧构建打的，新配置不在里面） |
| Redis 用哪个 db 都行 | **必须 db3**（dev K8s ConfigMap `SPRING_REFILES_DATABASE=3`，OAuth token context 写 db3，用错 db 报 REQUEST_408） |

### 1.5 DDL 是手工的

- 无 Flyway/Liquibase，SQL 文件按日期命名（`ddl/20260509-xxx.sql`）
- schema 前缀经常写死某个环境，跨环境执行前问 DBA
- 新表/改表：DBA 跑 DDL，不是应用启动自动建
- **字段含义全靠 `COMMENT ON COLUMN`**——查表结构时必须连 comment 一起查

---

## 二、V-IPD 特有的坑（通用清单）

| 类别 | 典型失败 | 进场时怎么防 |
|------|----------|----------------|
| JDK 版本 | 用了默认 JDK 17 → `Mapped Statements collection does not contain value`（mapper 静默加载失败） | 必须 JDK 8（`C:\Program Files\Java\jdk1.8.0_491`） |
| 内存 | 12 服务同时起 + 前端首编译 → 全挂 | 一期 `-Xmx512m`，二期 `-Xmx256m`；先编译前端再起 Java |
| pathing.jar | `找不到或无法加载主类` | manifest 不能有 BOM；目录条目必须以 `/` 结尾 |
| GatewayFilter | 登录报"非法请求"（6010101） | local 配置 `client.gateway.disable: true`，同步 target/classes |
| Redis db | `REQUEST_408` | local Redis database 改 3（main 和 identify 两处） |
| 端口冲突 | dvp/experience 都 18083 | experience 已改 18082，勿改回 |
| 上游同步 | 改了 iform-* 模块，下次同步被覆盖 | 定制代码只写 pp-* 模块 |
| 表风格混用 | 在 extends_ 表里写 `deleted_='N'` | 先看表前缀，按《数据库设计规范》两套风格分 |
| Feign 路由 | `Load balancer does not have available server` | local 下 Nacos discovery 关了，必须配 Ribbon `listOfServers: localhost:<端口>` |
| 菜单 404 | `defaultUrl` 带 `.vue` 后缀被 catch 吞掉 | 菜单 URL 不带 `.vue` 后缀 |
| 前端构建 | `pnpm build` OOM exit 134 | `--openssl-legacy-provider --max-old-space-size=8192` |
| ESLint 噪音 | dev 启动刷 400+ error | 历史债，lintOnSave 已降 warning，不阻塞 |
| 验收遗留 | 测试用例仅覆盖 55% 功能项 | 新功能必须补测试用例，见《测试策略总览》 |

---

## 三、和 AI 协作的规矩

1. **先写清口径再写代码。** 一句话产品描述，AI 能在两种实现里来回改；写进规格才稳。
2. **AI 说"表里有字段 X"必须查库验证。** 用 psycopg2 连测试库 `describe` 或 `SELECT`。
3. **改业务代码前先确认落点。** 一期业务 → `pp-project-root`/`pp-document-root`；二期 → 对应 `pp-*-root`；平台能力 → 原则上不改（上游覆盖）。
4. **测出问题先记清单，确认后再改。** 避免 AI 把交互、文案、接口方法一并"顺手优化"。
5. **听不懂就停。** 要求 AI 用"用户点了什么 → 读/写哪张表的哪一列 → 页面上会变成什么"解释。
6. **两期接口契约不要猜。** 二期调一期只走 `iform-integration-layer` 的 SDK（OAuthSdk/OrgSdk/FormSdk/MessageSdk/FileSdk/TodoSdk），不要自己写 Feign。

### 口径优先级（写死）

```text
1. 产品当场改口 / 已记录的决策
2. 规格最高版本
3. 现网库里查到的事实（psycopg2 连测试库）
4. 当前代码
5. PRD（可能落后，只当背景）
```

---

## 四、进场当天最短清单

1. 三个仓的本地路径、当前联调环境、vue proxy 打到哪。
2. psycopg2 能连测试库（`10.82.45.158:8000`）并 `describe` 一张表。
3. JDK 8 路径确认（不是默认 java 17）。
4. 这次需求改哪期：一期（pp-* 模块）还是二期（pp-*-root）？表前缀是 `pp_` 还是 `extends_`？
5. 要不要本地起服务？要的话看 `./skills/run-powerproject-backend/SKILL.md`，先想内存策略。

动手前能回答：

- 我要改的表，逻辑删除字段是哪个、正常值是几？
- 这个功能是硬编码还是 iform 动态表单配置的？
- 本地起服务的话，Redis db 是 3 吗？配置同步到 target/classes 了吗？

答不上来，先补齐 §一、§二，再让 AI 写代码。

---

## 五、变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| V1.0 | 2026-10-09 | 首次创建：三仓结构、两代后端差异、数据库连接与对账、本地启动坑、AI 协作规矩 |
