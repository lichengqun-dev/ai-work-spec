---
source: java后端开发规范.md
source_hash: sha256:cd8c17a3fad01f1d
extracted_at: 2026-10-21T11:27:52+08:00
extracted_by: ai-spec-extract
---

# 提炼自 `java后端开发规范.md`

_（**派生副本**：散文改了要重新提炼，否则构建报「源文档已变更」并在快照顶部标注。条目正文照抄散文，不做改写——约束的限定条件一概括就丢。）_

## STD-PRJ-V-IPD-004 · 统一响应结构：一期 `iform-basic-response`，二期 `pp-common-root` 封装

<!-- meta
tier: resident
scope: Controller / Service 编写
-->

**规则**：接口返回走各期既有的统一封装——**一期 `iform-basic-response`，二期 `pp-common-root`**。Controller 不吞异常，统一异常处理器兜底。**错误码沿用各期既有体系，不自造。不要新造一套返回结构**——前端要按返回结构写解析，多一套就多一套分支。

**原因**：两期各有一套已在用的封装，被大量 Controller 依赖。新造一套不会报错，只会让前端在同一个页面上处理两种结构；而**异常被吞掉**（catch 后返回一个"看起来成功"的结构）会让缺陷逃到生产。

## STD-PRJ-V-IPD-005 · 二期调一期平台能力只走 `iform-integration-layer` 的 SDK，禁止自己写 Feign

<!-- meta
tier: resident
scope: 跨服务调用、调用一期能力
-->

**规则**：二期调一期的认证、组织、表单、消息、文件、待办能力，**一律通过 `iform-integration-layer` 提供的 SDK**：

```java
// 正确：注入 SDK
@Autowired private OrgSdk orgSdk;
// 禁止：自己写 Feign 直调一期接口
```

SDK 清单：`OAuthSdk` / `OrgSdk` / `FormSdk` / `MessageSdk` / `NotifySdk` / `FileSdk` / `PlatformSdk` / `PpProject*Sdk` / `TodoSdk` / `BusinessTaskTodoSyncSdk`。
引入方式：依赖 `iform-integration-root/iform-integration-layer`；鉴权由拦截器自动带内部密钥 `authorization.secret.inner`。

**原因**：自己写 Feign 会**漏掉 Token / TraceId 透传与内部鉴权头注入**——调用链在链路追踪系统里断开，且内部鉴权头缺失会在一期侧被拒。这类缺失只在需要排查的那一天才被发现。见基线 `STD-BASE-402`。

## STD-PRJ-V-IPD-006 · 二期服务路由前缀走 `app.route.prefix` 配置，Controller 不硬编码

<!-- meta
tier: resident
scope: 新增模块、新增接口路径
-->

**规则**：二期各模块统一通过配置项 `app.route.prefix: /pp/<域>/v1` 维护网关前缀，**不要在 Controller 上硬编码完整路径**。

**原因**：前端所有请求走 `/gateway/iform` 单入口，网关按前缀分发到各服务。前缀写进 Controller 后，改一次网关规则就要全模块改代码；写进配置则只改一处。**这是本项目"网关前缀与代码解耦"的既有做法，新模块要跟上。**

## STD-PRJ-V-IPD-013 · JDK 必须 1.8，不用 JDK 17

<!-- meta
tier: resident
scope: 本地启动、构建、排查 mapper 加载失败
-->

**规则**：一期与二期后端**都强制 JDK 1.8**。本地路径 `C:\Program Files\Java\jdk1.8.0_491`，不要用默认的 JDK 17。

**JDK 17 下的三个具体故障**（不是"可能有问题"，是确定会发生）：
1. **JAXB 缺失 → MyBatis mapper 静默加载失败**，报 `Mapped Statements collection does not contain value`。一期的自研 `IformMybatisSqlSessionFactoryBean` 用 JAXB 解析 mapper XML，**找不到不报错**
2. 需要 `--add-opens` × 3
3. `MethodHandles$Lookup.IMPL_LOOKUP` 反射受限

**原因**：第 1 条的失败形态最麻烦——它**在启动时不报错**，只在调用到那个 mapper 时才暴露，而错误信息指向"语句不存在"，排查方向会被带到 XML 路径上去。

## STD-PRJ-V-IPD-014 · 一期的 `iform-*` 模块不要改，定制代码收敛到 `pp-*` 模块

<!-- meta
tier: resident
scope: 判断改代码落在哪
-->

**规则**：一期后端来自 iform 上游 SVN **单向同步**。**对 `iform-*` 模块的本地改动会在下次同步时被覆盖**。定制代码只写 `pp-project-root` / `pp-document-root`；确需改平台行为时，把定制副本放 `pp-*` 或用配置实现。

**原因**：这不是风格偏好，而是**改动会被物理覆盖**。代码写完能跑、测试能过，直到下一次上游同步——那时改动消失，且不会有人立刻发现。二期后端不在此约束内（9 个模块全部自主维护）。

## STD-PRJ-V-IPD-015 · 禁止在循环内以 INFO 级别打印大对象 JSON

<!-- meta
tier: indexed
scope: 写日志
-->

**规则**：禁止在循环里按 INFO 打大对象 JSON。**这是本项目的历史债，二期已清理多处，不要再引入。**
日志级别约定：INFO 业务事件、DEBUG 明细、WARN 可恢复异常、ERROR 需人工介入。

**原因**：循环内打大对象会让日志量随数据量线性放大，而日志框架是同步写的——**接口 RT 随数据量变长**，压测时才暴露。敏感信息不进日志见基线 `STD-BASE-102`。

## STD-PRJ-V-IPD-016 · 新增核心 Service 逻辑必须带 JUnit 5 单测

<!-- meta
tier: indexed
scope: 写后端业务逻辑
-->

**规则**：新增**核心 Service 逻辑**必须带 JUnit 5 单测，命名 `{被测类}Test`。二期改完本地起服务（~2 分钟）冒烟再提交；一期启动 3~9 分钟，至少跑一次核心链路（登录 + 主列表接口）。

**现状要说清**：后端测试基本为 0（二期 `target/test-classes` 是空壳）。**"现状为 0"不是豁免这条的理由**——正因为它为 0，新增的写入热点才更需要守卫。守卫目标优先级见《测试策略总览》§三。

