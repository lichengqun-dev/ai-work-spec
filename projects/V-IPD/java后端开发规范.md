# Java 后端开发规范

> 项目：V-IPD
> 最后更新：2026-10-09
> 级别：强制（除非标注"推荐"）
> 说明：V-IPD 两代后端技术栈不同，规范分两节。通用规范（命名/异常/日志）两期共用。

---

## 一、通用规范（两期共用）

### 1.1 环境

| 项 | 要求 |
|----|------|
| JDK | **1.8（强制）**。JDK 17 有三个假问题：JAXB 缺失 → MyBatis mapper 静默加载失败；需 `--add-opens`×3；`MethodHandles$Lookup.IMPL_LOOKUP` 反射受限 |
| 编码 | UTF-8（maven-compiler-plugin 显式声明） |
| 构建 | Maven 3.6.3，settings 用 `C:\Users\perso\.m2\settings-vipd.xml`，profile `voyah-profile` |
| 私服 | `http://mirrors.voyah.cn/repository/maven-releases/` |

### 1.2 命名

| 类型 | 规范 | 示例 |
|------|------|------|
| 包 | `com.ak.iform.<模块>.<分层>`（一期）/ `com.pp.<域>`（二期） | `com.pp.performance.controller` |
| 类 | PascalCase + 分层后缀 | `PpProjectController` / `CarPerformanceServiceImpl` / `PpProjectMapper` |
| 实体 | 表名驼峰：`pp_project` → `PpProject`；`extends_dvp_process` → `DvpProcess`（extends_ 前缀通常省略） | |
| 方法 | camelCase，动词开头 | `findMyTodos` / `saveTargetSet` |
| 常量 | UPPER_SNAKE | `MAX_PAGE_SIZE` |
| 测试类 | `{被测类}Test` | `PpProjectServiceTest` |

### 1.3 分层结构（二期标准，一期参照）

```
com.pp.<域>/
├── controller/     # REST 控制器（113 个现存 Controller 均此风格）
├── service/        # 业务接口 + impl/
├── mapper/         # MyBatis-Plus Mapper 接口
├── entity/         # 数据库实体（PO，@TableName）
├── dto/ vo/        # 传输/视图对象
├── config/         # 配置类
└── util/           # 工具
```

二期允许按业务子域再分包（performance 的 bpmn/car/filter/permission/template/...，dvp 的 api/base/data/process/scheduler/version），不强制统一。

### 1.4 异常与响应

- 统一响应结构（一期 `iform-basic-response`，二期 `pp-common-root` 封装）
- Controller 不吞异常，统一异常处理器
- 错误码沿用各期既有体系，不自造

### 1.5 日志

- 一期 Log4j2 + SLF4J；二期 Spring Boot 默认（logback）
- 禁止循环内 INFO 打大对象 JSON（历史债：二期已清理多处，勿再引入）
- 日志级别：INFO 业务事件，DEBUG 明细，WARN 可恢复异常，ERROR 需人工介入

### 1.6 安全红线

- SQL 一律参数化（`#{}`），禁止 `${}` 拼接（排序字段等确需拼接处白名单校验）
- 配置中的密码走环境变量（`${VAR:default}` 模式），新增配置禁止硬编码明文
- 内部服务间鉴权：二期调一期用 `authorization.secret.inner` 密钥对，不对外暴露
- 文件上传：校验类型/大小（spring.servlet.multipart 已限 500MB/600MB）

## 二、一期（powerprojectforjava-backend，iform 3.5.8）

### 2.1 技术栈

| 领域 | 技术 |
|------|------|
| 框架 | Spring Boot 2.3.12 + Spring Cloud Hoxton.SR12 + SCA（Nacos） |
| 通信 | Feign + Hystrix + Ribbon（local 用 listOfServers 静态路由） |
| ORM | MyBatis（自研 `IformMybatisSqlSessionFactoryBean`，JAXB 解析 mapper XML，**静默加载**——找不到不报错） |
| 数据源 | XML 多级加载：`dataSource-{cp}-{dbType}-{active}.xml → ... → dataSource.xml`；平台库独立 `dataSource-platform-*.xml`（MySQL） |
| 容器 | Undertow |
| 缓存 | Redisson + Jedis + Caffeine |
| 事务 | Seata |
| 线程池 | Hippo4j 动态线程池 |

### 2.2 代码落点（强制）

| 要改什么 | 去哪 | 说明 |
|---------|------|------|
| 一期项目管理业务 | `pp-project-root`（model/biz/provider/api/client 五件套） | |
| 一期文档业务 | `pp-document-root`（五件套） | |
| iform-* 平台模块 | **原则上不改** | 上游 SVN 单向同步，本地改动会被覆盖 |
| 确需改平台行为 | 定制副本放 pp-* 或通过配置 | |

### 2.3 一期特有约束

1. **数据源 XML**：GaussDB 配置在 `conf/dataSource-postgres-local.xml`（`db.dbType=postgres` 优先加载）；`dataSource-platform-local.xml` 指向 MySQL 平台库，**删掉会导致 platform/oauth 启动失败**
2. **GatewayFilter**：local 必须 `client.gateway.disable: true`（共享配置 `application-local-base.yml`）
3. **打包**：antrun 展开重组的 `xxx.jar + lib/`（非 fat jar），本地开发用 pathing.jar 方式启动（见 `./skills/run-powerproject-backend/SKILL.md`）
4. **新 Bean 注意包扫描**：启动类 `@ComponentScan` 范围外的新包不会被扫到
5. **MyBatis 静默加载**：mapper XML 放错位置不报错，运行时才发现 `Mapped Statements collection does not contain value`——新 mapper 先跑一次再提交

### 2.4 Feign 服务间调用

- 服务名：`iform-platform-provider` / `iform-business-provider` / `iform-oauthserver-provider` / `pp-project-provider` / `pp-document-provider`
- local 下必须配 Ribbon `listOfServers: localhost:<端口>`（Nacos discovery 关闭时 Feign 找不到服务）

## 三、二期（pp-powerproject-extend）

### 3.1 技术栈

| 领域 | 技术 |
|------|------|
| 框架 | Spring Boot 2.6.13 + Spring Cloud 2021.0.5 + SCA 2021.0.5.0（Nacos 1.4.6 client） |
| ORM | MyBatis-Plus（`assign_id` 主键、`map-underscore-to-camel-case`） |
| 通信 | OpenFeign + Spring Cloud LoadBalancer（ribbon 禁用） |
| 分页 | MyBatis-Plus 分页插件 |
| 文档 | SpringDoc OpenAPI（`/v3/api-docs` + `/swagger-ui.html`） |
| Excel | POI 5.2.5 |
| HTTP 客户端 | OkHttp 4.12 |

### 3.2 配置规范

- 每模块 `application.yml`（激活 `${SPRING_PROFILES_ACTIVE:dev}`）+ `application-{local,dev,test,prod}.yml`
- 环境变量全覆盖：`${VAR:default}`（Nacos/RabbitMQ/GaussDB/Redis/飞书）
- 路由前缀 `app.route.prefix: /pp/<域>/v1`（写在 yml，Controller 不硬编码）
- 数据源直配 yml（不走 XML）
- Nacos import：`optional:nacos:${spring.application.name}[-${profile}].yml`，group `ppExploit`

### 3.3 调一期平台能力（强制走 integration-layer）

```java
// 正确：通过 SDK
@Autowired private OrgSdk orgSdk;
@Autowired private MessageSdk messageSdk;

// 禁止：自己写 Feign 直调一期接口
```

- SDK 清单：`OAuthSdk` / `OrgSdk` / `FormSdk` / `MessageSdk` / `NotifySdk` / `FileSdk` / `PlatformSdk` / `PpProject*Sdk` / `TodoSdk` / `BusinessTaskTodoSyncSdk`
- 引入方式：依赖 `iform-integration-root/iform-integration-layer`
- 鉴权：内部密钥 `authorization.secret.inner`（Feign 拦截器自动带头）

### 3.4 实体与 Mapper

```java
@Data
@TableName("extends_dvp_process")
public class DvpProcess {
    @TableId(type = IdType.ASSIGN_ID)
    private String id;          // varchar(32)
    private String dvpNo;
    private Integer isDeleted;  // 1=正常（注意与常见约定相反）
    @Version
    private Integer lockVersion; // 有此字段的表才加
    // ...
}
```

- 查询必须带逻辑删除条件（`is_delete=1` 或 `is_deleted=1`，以表 COMMENT 为准）
- 二期 34 个 XML mapper 放 `src/main/resources/mapper/`，复杂 SQL 写 XML，简单 CRUD 用 MP

### 3.5 飞书集成

- SDK：`oapi-sdk`（app-id/secret 走环境变量 `FEISHU_APP_ID/FEISHU_APP_SECRET`）
- tenant_access_token 缓存 Redis（key `feishu:tenant_access_token`，expire-buffer 300s）
- 消息推送场景：cmf/competitor/specialised-parts 模块

### 3.6 版本快照写入模式（performance/experience 模式）

新增带版本的业务表时，参照既有三级结构：主表 + `_versions`（版本表）+ `_version_items`（明细版本表）+ `source_template_snapshot`（jsonb 来源快照）。写版本表与主表在同一事务。

## 四、数据库访问规范（两期）

详细见《数据库设计规范》。要点：

1. 查询必须带逻辑删除条件（一期 `deleted_='N'`，二期 `is_delete=1`）
2. 共享 SQL 片段参数必须全量 `@Param` 声明
3. 禁止 `SELECT *`、N+1、大事务
4. GaussDB 保留字加双引号
5. 分页：一期 PageHelper，二期 MP 分页插件

## 五、测试要求

- 现状：后端测试基本为 0（二期 target/test-classes 空壳）
- 新增核心 Service 逻辑必须带 JUnit 5 单测（守卫目标见《测试策略总览》§三）
- 二期启动快（~2 分钟），改完本地起服务冒烟再提交
- 一期启动慢（3~9 分钟），至少跑一次核心链路（登录 + 主列表接口）
