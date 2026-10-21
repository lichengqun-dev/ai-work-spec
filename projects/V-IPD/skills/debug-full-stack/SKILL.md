---
name: debug-full-stack
description: V-IPD 前后端本地联调全景：启动顺序、混合模式（本地服务 + dev OAuth）、断点调试、请求链路追踪、数据库对账、常见问题定位。当用户要联调前后端、排查接口走哪个后端、打断点、对数据时使用。
---

# V-IPD 前后端本地联调（debug-full-stack）

> 单项启动手册：一期后端 `../run-powerproject-backend/SKILL.md`、二期 `../run-pp-extend/SKILL.md`、前端 `../run-frontend/SKILL.md`。
> 本篇讲**组合与排查**：什么顺序起、请求链路怎么走、断点怎么打、数据怎么对。

## 一、联调模式选择

| 模式 | 起什么 | 适用场景 |
|------|--------|---------|
| **A 全本地** | 5 一期 + 7 二期 + 前端（12+1） | 改动跨前后端，需要断点 |
| **B 混合模式**（推荐起步） | 本地改的服务 + 其余走 dev（OAuth 走 dev 代理） | 只改个别服务 |
| **C 纯前端** | 只起前端，全部走兜底 → core-dev | 只改前端页面 |
| **D 登录最小集** | oauth + platform + business + project（4 一期）+ 前端 | 只需要登录后调一期接口 |

模式 B/C 依赖代理矩阵见 `../run-frontend/SKILL.md` §三：**不想本地起的服务，注释掉 vue.config.js 对应 localhost 规则，自动兜底到 core-dev**。

## 二、启动顺序（全本地模式 A）

```
1. 后端构建：pathing.jar 已就绪则跳过（见各 SKILL）
2. 配置同步：改过 yml 必须复制到 target/classes
3. 起 Java（内存：一期 512m / 二期 256m）
   3.1 一期按依赖序：oauth(6200) → platform(6300) → business(6305) → project(6500) → document(6400)
   3.2 二期任意序（互不依赖）：18081-18087 按需
4. 验证后端：health 200 + Started 日志
5. 起前端（首次编译 ~4GB 内存；若内存不足先等前端编译完再起 Java——顺序反转）
6. 验证：9528 返回 200 → 登录
```

**16GB 机器实操建议**：先起前端等编译完（Java 全停），再起 Java 12 个。8GB+ 内存机器顺序随意。

## 三、请求链路追踪（排查接口问题的标准流程）

```
浏览器 → http://localhost:9528
  └→ vue proxy 按 URL 前缀匹配（vue.config.js devServer.proxy）
      ├ /gateway/iform/oauth2/v3/**  → localhost:6200（oauth，剥前缀）
      ├ /gateway/iform/platform/v3/** → localhost:6300
      ├ /gateway/iform/business/v3/** → localhost:6305
      ├ /gateway/iform/pp-project/v3/** → localhost:6500
      ├ /gateway/iform/pp-document/v3/** → localhost:6400
      ├ /gateway/iform/pp/<alias>/v1/** → localhost:18xxx（只剥 /gateway/iform）
      ├ ^/gateway（兜底）→ core-dev.voyah.cn
      ├ ^/dhtmlx → core-dev（甘特导出）
      └ ^/api → e签宝（esignoss，非主后端）
```

**排查四步**：

1. **DevTools Network 看 URL 前缀** —— 确定走哪条代理规则
2. **看 target 是 localhost 还是 core-dev** —— localhost 请求失败 = 本地服务没起/挂了；core-dev 请求异常 = dev 环境问题（不是你的代码）
3. **对照端口表** —— 6200/6300/6305/6400/6500（一期）+ 18081-18087（二期）
4. **后端日志** —— `Get-Content target\vipd-start.log -Tail 50 -Wait`（或 `-wait` 实时滚）

## 四、认证链路（本地联调的核心）

```
登录 → oauth(6200) 发 token → 写 Redis 10.82.71.250:6379 db3
后续请求带 token → 各服务（一期/二期）从同一 db3 读 token context 校验
```

**三条铁律**：

1. **Redis 必须 db3**：一期 `application-local-base.yml`、二期各 `application-local.yml` 已统一改为 db3（2026-10-09）。dev K8s ConfigMap `SPRING_REFILES_DATABASE=3`，两边不一致 → `REQUEST_408`
2. **GatewayFilter 必须关**：`client.gateway.disable: true`（一期共享配置），否则 vue proxy 直连报"非法请求"6010101
3. **改配置必须同步 target/classes**：jar 是旧构建，yml 改了不复制不生效

### 混合模式（B）的认证

本地服务 + dev OAuth 可行：OAuth 在 dev 写 db3（K8s ConfigMap），本地服务从同一 db3 读 → 校验通过。前提：本地 Redis 配置 = db3 + 相同 Redis 实例（10.82.71.250）。

## 五、断点调试

### 5.1 后端（IDEA 远程 debug）

一期/二期都是 pathing.jar 启动，加 JVM debug 参数即可：

```powershell
# 以 cmf 为例（端口 18087，debug 端口 5005 自选不冲突即可）
& $java8 -Xmx256m -agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=5005 `
  -cp "$modDir\target\pathing.jar" com.pp.cmf.PpCMFApplication *> "$modDir\target\vipd-start.log"
```

- IDEA：Run → Attach to Process 或 Remote JVM Debug（host localhost, port 5005）
- `suspend=n` 不等待断点连接即启动；想启动就断住用 `suspend=y`
- **12 个服务同时 debug**：每个服务配不同 debug 端口（5005/5006/5007...）
- 断点建议：Controller 入参 → Service 关键分支 → Mapper 前后

### 5.2 热改代码流程

改 Java → 重编译该模块（`mvn compile` 或 IDEA build）→ **重启该服务**（pathing.jar 的 classes 目录是引用的，重编译后重启即生效）：

```powershell
# 重编译（增量，秒级）
cmd /c "`"$mvn`" -f `"$modDir\pom.xml`" -s `"C:\Users\perso\.m2\settings-vipd.xml`" compile -q"
# 重启服务（先停旧进程再启动）
```

注意：重编译后 **pathing.jar 不用重新生成**（它引用 classes 目录），除非改了依赖（pom）。

### 5.3 前端

- dev server 自带热更新（HMR），改 .vue/.js 即时生效
- Vue Devtools 浏览器插件看组件树/Vuex
- ESLint 满屏红是历史债，不影响

## 六、数据库对账（验证接口返回的数据）

```python
# psycopg2 连测试库
import psycopg2, json
conn = psycopg2.connect(host="10.82.45.158", port=8000,
    dbname="PowerProject6_20260512", user="pp", password=os.environ["PP_TEST_DB_PASSWORD"],   # 口令不写死在脚本里
    options="-c search_path=public")
cur = conn.cursor()
cur.execute("SELECT count(*) FROM pp_project WHERE deleted_='N'")     # 一期：deleted_='N'
print(cur.fetchone())
cur.execute("SELECT count(*) FROM extends_dvp_process WHERE is_deleted=1")  # 二期：is_delete=1（1=正常！）
print(cur.fetchone())
```

**逻辑删除值域（易错）**：一期 `deleted_='N'`=正常；二期 `is_delete=1`=正常（与常见约定相反）。

对账模式：接口返回的 total/rows vs DB SELECT 结果一致 → 数据链路正常。

## 七、常见联调问题速查

| 症状 | 定位 | 解决 |
|------|------|------|
| 登录"非法请求"（6010101） | GatewayFilter 拦截（本地请求没网关密钥头） | `client.gateway.disable: true` + 同步 target/classes + 重启 |
| `REQUEST_408` | 本地与 OAuth 的 Redis db 不一致 | 两边都 db3（已统一，若复现检查是否环境变量覆盖了 db） |
| 接口 401 | token 没带/过期/OAuth 没起 | DevTools 看 Authorization 头；确认 6200 起了；前端用裸 JWT（无 `Bearer ` 前缀） |
| 接口打到 core-dev 而不是本地 | 对应服务没起，代理兜底 | 起该服务；或确认注释代理规则是有意的 |
| Feign `Load balancer does not have available server` | Nacos discovery 关了但目标服务没起 | 起目标服务；Ribbon listOfServers 指向 localhost |
| 二期调一期 401/失败 | 一期 OAuth/目标服务没起，或 Redis db 不一致 | 起最小集 4 个一期服务；db3 |
| 改了 Java 代码不生效 | 没重编译/没重启/pathing.jar 过期 | `mvn compile` + 重启；pom 变了才重新生成 pathing.jar |
| 改了 yml 不生效 | 没复制到 target/classes | Copy-Item src→target/classes 后重启 |
| 断点不命中 | attach 错进程/端口，或 suspend=n 时启动早于 attach | 确认 debug 端口；已过断点位置的请求重新发 |
| 页面白屏/404 无报错 | 菜单 defaultUrl 带 `.vue` | 去掉后缀 |
| 前端代理 502 | target localhost 服务没起 | netstat 确认端口 LISTENING |

## 八、最小可用组合（快速起步）

只想**登录 + 调通一期项目接口**：

```
oauth(6200) + platform(6300) + business(6305) + project(6500) + 前端
= 4 Java（512m×4 = 2GB）+ 前端（4GB 编译）
```

想**调二期某服务**（如 cmf）：上述 4 个 + cmf(18087)。

**全量**：12 Java（一期 512m×5 + 二期 256m×7 ≈ 4.3GB 常驻）+ 前端 ≈ 需 12GB+ 机器。

## 九、停服与清理

```powershell
# 停全部 Java（后端）
Get-Process -Name java -ErrorAction SilentlyContinue | Stop-Process -Force
# 停前端
Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq "" } | Stop-Process -Force
# 确认端口清空
netstat -ano | Select-String ":(6200|6300|6305|6400|6500|1808[1-7]|9528) "
```

测试数据清理：逻辑删除（保留对账），前缀 `V-IPD-TEST-`。
