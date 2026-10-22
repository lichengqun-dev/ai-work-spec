---
name: run-powerproject-backend
description: 在本地启动 V-IPD 完整开发环境：一期后端 powerprojectforjava-backend（5 服务）、二期后端 pp-powerproject-extend（7 服务）、前端 powerprojectforjava-frontend。涵盖 JDK 8 要求、pathing.jar 生成、vue proxy 配置、GatewayFilter 关闭、内存限制、常见坑。当用户要求启动、停止、调试本地服务或前端连本地后端时使用。
---

# V-IPD 本地开发环境（一期 + 二期 + 前端）

## 三个项目（用户说"一、二期后端"时对应关系）

| 简称 | 项目 | 说明 |
|------|------|------|
| 一期后端 | `powerprojectforjava-backend` | iform 框架，5 个服务，重（启动 3~9 分钟） |
| 二期后端 | `pp-powerproject-extend` | Spring Boot + MyBatis-Plus，7 个服务，轻（启动 ~2 分钟） |
| 前端 | `powerprojectforjava-frontend` | Vue 2.6 + Vue CLI，端口 9528 |

## 硬性要求：JDK 8

**必须用 JDK 8**（`C:\Program Files\Java\jdk1.8.0_491`）。机器默认 `java` 是 17，**不要用**。

JDK 17 会产生三个假问题（JDK 8 下全部不存在）：
- JAXB 运行时缺失 → MyBatis mapper 静默加载失败（`Mapped Statements collection does not contain value`）
- 需要 `--add-opens` × 3
- `MethodHandles$Lookup.IMPL_LOOKUP` 反射受限

## 一期 5 个服务

| 服务 | 模块路径（相对 powerprojectforjava-backend） | 主类 | 端口 |
|------|------|------|------|
| project | `pp-project-root\modules\pp-project-provider-root\modules\provider-pp-project` | `com.ak.iform.PPprojectApplication` | 6500 |
| business | `iform-provider-root\modules\provider-business` | `com.ak.iform.BusinessApplication` | 6305 |
| platform | `iform-provider-root\modules\provider-platform` | `com.ak.iform.PlatformApplication` | 6300 |
| oauth | `iform-oauth-root\modules\oauth-server2` | `com.ak.iform.OAuth2ServerApplication2` | 6200 |
| document | `pp-document-root\modules\pp-document-provider-root\modules\provider-pp-document` | `com.ak.iform.DocumentApplication` | 6400 |

## 二期 7 个服务

| 服务 | 模块（相对 pp-powerproject-extend） | 主类 | 端口 | 路由前缀 |
|------|------|------|------|------|
| performance | `pp-performance-root` | `com.pp.performance.PpPerformanceApplication` | 18081 | /pp/performance/v1 |
| experience | `pp-experience-root` | `com.pp.experience.PpExperienceApplication` | 18082 | /pp/experience/v1 |
| dvp | `pp-dvp-root` | `com.pp.dvp.PpDvpApplication` | 18083 | /pp/dvp/v1 |
| experience-issue | `pp-experience-issue-root` | `com.pp.experienceissue.PpExperienceIssueApplication` | 18084 | /pp/experience-issue/v1 |
| specialised-parts | `pp-specialised-parts-root` | `com.pp.specialisedparts.PpSpecialisedPartsApplication` | 18085 | /pp/specialised-parts/v1 |
| competitor | `pp-competitor-root` | `com.pp.competitor.PpCompetitorApplication` | 18086 | /pp/competitor/v1 |
| cmf | `pp-cmf-root` | `com.pp.cmf.PpCMFApplication` | 18087 | /pp/cmf/v1 |

⚠️ experience 端口已从 18083 改为 18082（原与 dvp 冲突，dev 环境不同 pod 不冲突，本地会撞端口）。

二期服务**自带路由前缀**（`app.route.prefix`），如 CMF 的接口是 `http://localhost:18087/pp/cmf/v1/...`。

## local 环境基础设施

| 组件 | 地址 | 凭据 |
|------|------|------|
| GaussDB | `jdbc:postgresql://10.82.45.158:8000,10.82.45.1:8000/PowerProject6` | `pp` / `V0y@hFre!` |
| Redis | `10.82.71.250:6379` **db3** | `cred888888`（一期共享配置 `application-local-base.yml`；二期各模块 `application-local.yml`）。**必须用 db3**：dev K8s ConfigMap 设 `SPRING_REDIS_DATABASE=3`，OAuth 把 token context 写在 db3，本地用其他 db 会报 REQUEST_408 |
| Nacos | `10.82.45.10:8848` group `ppExploit` | 密码 `V0y@hFre!`，**discovery 与 ribbon 均关闭** |
| RabbitMQ | `10.82.45.211:5672` | `V0y@hFre!` |
| iform 平台库 | MySQL `47.113.205.64:3306/iform_v357` | auth/desktop 表在这里，**不在 GaussDB**（仅一期需要） |

## 关键配置（已就绪，勿重复创建）

### 一期共享配置（`iform-basic-root\modules\basic-response\src\main\resources\config\`）

- `application-local-base.yml` — Redis/RabbitMQ/Kafka/ES + **Ribbon 静态路由** + **client.gateway.disable: true**
- `application-local-nacos.yml` — Nacos（discovery/ribbon 全关）
- `application-local-esign.yml`、`application-local-socket.yml`

**Ribbon 静态路由**（服务间 Feign 直连 localhost，不走 Nacos）：
```yaml
ribbon:
  eureka:
    enabled: false
  NIWSServerListClassName: com.netflix.loadbalancer.ConfigurationBasedServerList

iform-platform-provider:
  ribbon:
    listOfServers: localhost:6300
# ... business:6305, oauth:6200, project:6500, document:6400
```

**GatewayFilter 关闭**（关键！否则登录报"非法请求"）：
```yaml
client:
  gateway:
    disable: ${CLIENT_GATEWAY_DISABLE:true}
```
原理：`GatewayFilter` 校验请求必须带网关密钥 header。线上请求经过网关自动带头；本地 vue proxy 直连服务没有这个头，被拦截。`disable: true` 放行。

### 一期每模块配置（`<模块>\src\main\resources\`）

- `config\application-local.yml` — 端口 + `include: local-base,local-nacos,...`
- `conf\dataSource-postgres-local.xml` — **主数据源**（GaussDB）。`db.dbType=postgres` 时优先加载
- `conf\dataSource-local.xml` — 回退数据源
- `conf\dataSource-platform-local.xml` — **必需**（business/platform/oauth）。指向 iform 平台库 MySQL，删掉会导致 platform 启动失败

### 二期每模块配置（`<模块>\src\main\resources\application-local.yml`）

- 数据源直接写在 yml 里（spring.datasource.url 指向 GaussDB）
- Nacos discovery 关闭（`NACOS_DISCOVERY_ENABLED:false`）
- 各服务独立的业务配置（飞书、VHome 等）

## 前端 vue.config.js proxy（已配置）

`devServer.proxy` 按服务拆分，`/gateway/iform/<路径>` 转发到本地后端：

- **一期**：`^/gateway/iform/<alias>/v3` → 剥掉整个前缀 → `localhost:<端口>`（等价网关 StripPrefix=3）
  - platform/v3→6300, business/v3→6305, oauth2/v3→6200, pp-project/v3→6500, pp-document/v3→6400
- **二期**：`^/gateway/iform/pp/<alias>/v1` → 只剥 `/gateway/iform` → `localhost:<端口>`（服务自带前缀）
  - pp/cmf/v1→18087, pp/dvp/v1→18083, pp/performance/v1→18081, pp/experience/v1→18082, pp/experience-issue/v1→18084, pp/specialised-parts/v1→18085, pp/competitor/v1→18086
- **兜底**：未匹配的 `^/gateway` 走 `https://core-test.voyah.cn`（报表等）；`^/dhtmlx`（甘特导出）走 core-test
- `^/api` 走 esign（电子签名，与主后端无关）

## 启动步骤

### 0. 内存策略（16GB 机器必读）

**不要同时启动 12 个服务 + 前端首次编译** — 会 OOM 全挂。

- Java 默认最大堆 = 物理内存 1/4 = 4GB/服务，12 个服务理论峰值 48GB，必挂
- **必须加 `-Xmx` 限制**：一期 `-Xmx512m`，二期 `-Xmx256m`
- **登录最小集**：oauth + platform + business + project（4 个一期服务）
- **前端首次编译需要 ~4GB 内存**：如果内存不足，先停 Java 进程，等前端编译完（`http://localhost:9528/` 返回 200）再启动 Java

### 1. 一期：构建 classpath + pathing.jar（每模块一次，依赖变了才需重跑）

```powershell
$mvn = "C:\Users\perso\.m2\apache-maven-3.6.3\bin\mvn.cmd"
$modDir = "<powerprojectforjava-backend>\<模块路径>"
cmd /c "`"$mvn`" -f `"$modDir\pom.xml`" -s `"C:\Users\perso\.m2\settings-vipd.xml`" org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath -Dmdep.outputFile=`"$modDir\target\cp.txt`" -q"
```

必须用 `cmd /c` 包裹，PowerShell 直接调 mvn 会把 `-D` 参数拆错。

pathing.jar 生成（JDK 8 不支持 `@argfile`，classpath ~60KB 超命令行限制）：

```powershell
function New-PathingJar($jarOut, $entries, $baseDir) {
    $baseUri = [Uri]::new(($baseDir.TrimEnd('\') + '\'))
    $relPaths = foreach ($e in $entries) {
        if (-not $e) { continue }
        $full = [System.IO.Path]::GetFullPath($e.Trim())
        $rel = $baseUri.MakeRelativeUri([Uri]::new($full)).ToString()
        if (Test-Path $full -PathType Container) { $rel = $rel.TrimEnd('/') + '/' }
        $rel
    }
    $bytes = [System.Text.Encoding]::ASCII.GetBytes("Class-Path: " + ($relPaths -join " "))
    $result = New-Object System.Collections.Generic.List[string]
    $endIdx = [Math]::Min(71, $bytes.Length - 1)
    $result.Add([System.Text.Encoding]::ASCII.GetString($bytes[0..$endIdx]))
    $pos = $endIdx + 1
    while ($pos -lt $bytes.Length) {
        $endIdx = [Math]::Min($pos + 70, $bytes.Length - 1)
        $result.Add(" " + [System.Text.Encoding]::ASCII.GetString($bytes[$pos..$endIdx]))
        $pos = $endIdx + 1
    }
    $mf = "Manifest-Version: 1.0`r`n" + ($result -join "`r`n") + "`r`n`r`n"
    Add-Type -AssemblyName System.IO.Compression
    if (Test-Path $jarOut) { Remove-Item $jarOut -Force }
    $fs = [System.IO.File]::Create($jarOut)
    $zip = New-Object System.IO.Compression.ZipArchive($fs, [System.IO.Compression.ZipArchiveMode]::Create)
    $sw = New-Object System.IO.StreamWriter(($zip.CreateEntry("META-INF/MANIFEST.MF")).Open(), (New-Object System.Text.UTF8Encoding($false)))
    $sw.Write($mf); $sw.Close(); $zip.Dispose(); $fs.Close()
}

$depCp = (Get-Content "$modDir\target\cp.txt" -Raw).Trim() -split ";"
$entries = @("$modDir\target\classes") + ($depCp | Where-Object { $_.Trim() -ne "" })
New-PathingJar "$modDir\target\pathing.jar" $entries "$modDir\target"
```

**pathing.jar 两个致命坑**（都会导致"找不到或无法加载主类"）：
1. **目录条目必须以 `/` 结尾**（`classes/`），否则被当作 jar 文件
2. **manifest 不能有 BOM** — 用 `UTF8Encoding($false)` 或 ASCII

### 2. 二期：maven install + classpath + pathing.jar

```powershell
# 全量构建（~6 分钟，只需一次或依赖变更后）
cmd /c "`"$mvn`" -f `"<pp-powerproject-extend>\pom.xml`" -s `"C:\Users\perso\.m2\settings-vipd.xml`" clean install -DskipTests -q"

# 每模块 classpath（同一期）
cmd /c "`"$mvn`" -f `"<pp-powerproject-extend>\<模块>\pom.xml`" -s `"C:\Users\perso\.m2\settings-vipd.xml`" org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath -Dmdep.outputFile=`"<模块>\target\cp.txt`" -q"

# pathing.jar 用同一个 New-PathingJar 函数
```

### 3. 同步配置到 target/classes（改配置后必须做）

jar 是旧构建打的，新配置不在里面：

```powershell
# 一期：共享配置 + 模块配置
$sharedSrc = "<一期root>\iform-basic-root\modules\basic-response\src\main\resources\config"
foreach ($f in @("application-local-base.yml","application-local-nacos.yml","application-local-esign.yml","application-local-socket.yml")) {
    Copy-Item "$sharedSrc\$f" "$modDir\target\classes\config\" -Force
}
Copy-Item "$modDir\src\main\resources\config\application-local.yml" "$modDir\target\classes\config\" -Force
Get-ChildItem "$modDir\src\main\resources\conf" -Filter "dataSource*local*.xml" | ForEach-Object {
    Copy-Item $_.FullName "$modDir\target\classes\conf\" -Force
}

# 二期：只需复制 application-local.yml 和 application.yml
Copy-Item "$modDir\src\main\resources\application-local.yml" "$modDir\target\classes\" -Force
Copy-Item "$modDir\src\main\resources\application.yml" "$modDir\target\classes\" -Force
```

### 4. 启动服务（带内存限制）

```powershell
$env:SPRING_PROFILES_ACTIVE = "local"
$java8 = "C:\Program Files\Java\jdk1.8.0_491\bin\java.exe"

# 一期（-Xmx512m）
& $java8 -Xmx512m -Xms128m -cp "$modDir\target\pathing.jar" <主类>

# 二期（-Xmx256m）
& $java8 -Xmx256m -Xms128m -cp "$modDir\target\pathing.jar" <主类>
```

启动耗时：一期 3~9 分钟（schema 初始化 + 缓存加载），二期 ~2 分钟。
判断成功：日志出现 `Started <XxxApplication> on port(s) <端口>`。

### 5. 启动前端

```powershell
# 依赖已装好（node_modules 存在），Node 24 需 openssl legacy provider
cd <前端root>
$env:NODE_OPTIONS = "--openssl-legacy-provider --max-old-space-size=8096"
node "node_modules/@vue/cli-service/bin/vue-cli-service.js" serve --open
```

- 端口 9528，访问 `http://localhost:9528/`
- 首次编译 21000+ 模块，需要几分钟和 ~4GB 内存
- 编译中 HTTP 000 是正常的，等返回 200

## 验证

```powershell
# 前端页面
curl http://localhost:9528/                          # → 200

# 一期登录链路（GatewayFilter 已关）
curl http://localhost:9528/gateway/iform/oauth2/v3/user/captcha -X POST   # → 200（不再"非法请求"）

# 一期 API
curl http://localhost:9528/gateway/iform/pp-project/v3/api/userHome/findMyTodos -X POST -H "Content-Type: application/json" -d '{...}'

# 二期 API
curl http://localhost:9528/gateway/iform/pp/cmf/v1/base-assemblies -X POST -H "Content-Type: application/json" -d '{}'
```

## 常见错误速查

| 症状 | 原因 | 解决 |
|------|------|------|
| 登录报"非法请求"（6010101） | GatewayFilter 拦截（请求没带网关密钥 header） | `application-local-base.yml` 加 `client.gateway.disable: true`，同步到 target/classes 后重启 |
| 全部 Java 进程无声挂掉 | 内存 OOM（12 服务 × 默认 4GB 堆） | 加 `-Xmx512m`/`-Xmx256m`；不要 12 个服务 + 前端首编译同时跑 |
| 前端编译卡死/HTTP 000 超时 | 内存不足（Java 占满） | 停 Java 进程，等前端编译完（200）再启动 Java |
| `找不到或无法加载主类` | pathing.jar manifest 有 BOM，或目录条目缺尾部 `/` | 按规则重新生成 |
| `Mapped Statements collection does not contain value` | 用了 JDK 17（JAXB 缺失）或删了 `dataSource-platform-local.xml` | 换 JDK 8；恢复平台数据源文件 |
| `Port XXXX is already in use` | 上次进程没退干净 | `Get-Process java \| Stop-Process -Force` |
| 二期 dvp/experience 端口冲突 | 两个模块 local.yml 都写 18083 | experience 已改 18082，勿改回 |
| `Unable to connect to Redis server: localhost:6379` | 共享配置没复制到 target/classes | 执行配置同步步骤 |
| Feign 报 `Load balancer does not have available server` | Nacos discovery 关了但没配 Ribbon listOfServers | 确认 `application-local-base.yml` 的 Ribbon 静态路由在 target/classes 里 |
| Redis `RedisTimeoutException`（启动中） | 多服务同时启动的瞬时超时 | 非致命，忽略 |
| `REQUEST_408` 应用使用的redis与认证中心的redis不是同一个 | local Redis database ≠ dev 的 database。dev K8s ConfigMap 设 `SPRING_REDIS_DATABASE=3`（覆盖 yml 默认 10），但 local 配置写的 db9/db10 | `application-local-base.yml` 里 `database` 改成 **3**（main 和 identify 两处），同步到 target/classes 后重启 |

## 为什么不能直接调 dev 环境的服务

1. dev 服务注册的 IP 是 K8s 内网（192.168.x.x），本机不可达
2. dev 网关（core-dev.voyah.cn，HTTP 可达）能转发请求。**混合模式可行**：本地 project + dev OAuth（经代理 localhost:16200），前提是 local Redis database = **3**（和 dev K8s ConfigMap 的 `SPRING_REDIS_DATABASE=3` 一致），OAuth 把 token context 写在 db3，本地 project 从 db3 读 → 校验通过
3. 本地服务间走 Ribbon localhost 直连（listOfServers），OAuth 可走代理到 dev 或本地启动

## 前端构建补充（来自 powerprojectforjava-frontend/CLAUDE.md）

### 包管理器

- `package.json#packageManager` 声明 `yarn@1.22.21`，但 Node 24 下 yarn 1 会报版本错
- 仓库**没有任何锁文件**进 git（yarn/pnpm/npm 都没有）
- 本地推荐 pnpm，配合根目录 `.npmrc`（**不要提交**）：
  ```
  package-manager-strict=false
  shamefully-hoist=true
  strict-peer-dependencies=false
  auto-install-peers=true
  ```

### scripts 与多环境

| 任务 | 命令 | 备注 |
|------|------|------|
| 安装依赖 | `pnpm install` | 已验证 2m10s |
| 开发 | `pnpm run dev2`（脚本内已带 `NODE_OPTIONS=--openssl-legacy-provider`） | 或按本文 §5 用 `node vue-cli-service serve` |
| 生产构建 | `NODE_OPTIONS="--openssl-legacy-provider --max-old-space-size=8192" pnpm run build` | 已验证 5m14s |
| Bundle 分析 | 构建命令末尾加 `-- --report` | 自动弹 webpack-bundle-analyzer |
| 单测 | `pnpm run test:unit` | Jest，配置在 `jest.config.js`；现状无有效测试 |
| Lint | ⚠️ `pnpm run lint` 默认带 `--fix`，会改动 406 个历史 error | 慎跑；局部修用 `npx eslint --fix <file>` |
| i18n 报告 | `pnpm run i18n:report` | |

### 多环境交付目标

6 套 `.env`：`.env` / `.env.development` / `.env.staging` / `.env.production` / `.env.prod.test` / `.env.prod.boot` / `.env.prod.cloud`

对应 scripts：`build:prod:test` / `build:prod:boot` / `build:prod:cloud` / `build:stage`

说明存在 **测试云 / 私有化部署 / 公有云** 多套交付目标。

### Bundle 体积

- `chunk-vendor.js` 6.5MB 偏大（5 套表格方案 + ECharts + bpmn-js + Konva 等）
- 想优化时跑 `build -- --report` 看 bundle-analyzer，按需 code split

### 不要提交的文件

- `.npmrc`（影响用 yarn 的同事）
- `pnpm-lock.yaml`（与上游同步冲突）

## 来源

- 原 `.dsh/skills/run-powerproject-backend/SKILL.md`（本地仓库 `.dsh/` 目录）
- 前端补充整合自 `powerprojectforjava-frontend/CLAUDE.md`
- 2026-10-09 搬入 `alm-ai-doc/project/vipd/skill/`，供团队共享
