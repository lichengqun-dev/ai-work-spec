---
name: run-pp-extend
description: 在本地启动 V-IPD 二期后端 pp-powerproject-extend 的 7 个微服务（performance/experience/dvp/experience-issue/specialised-parts/competitor/cmf，端口 18081-18087）。涵盖 JDK 8 要求、pathing.jar 复用、Redis db3 对齐、启动命令、验证、常见坑。当用户要求启动、停止、调试二期服务时使用。
---

# V-IPD 二期后端本地启动（pp-powerproject-extend）

> 本篇专讲二期 7 个服务。一期 5 服务启动见 `../run-powerproject-backend/SKILL.md`。
> 二期比一期轻得多：pathing.jar 已就绪时单服务启动 ~11 秒（一期 3~9 分钟）。

## 一、二期 7 个服务

| 服务 | 端口 | 模块（相对 pp-powerproject-extend） | 主类 | 路由前缀 |
|------|------|------|------|------|
| performance | 18081 | `pp-performance-root` | `com.pp.performance.PpPerformanceApplication` | /pp/performance/v1 |
| experience | 18082 | `pp-experience-root` | `com.pp.experience.PpExperienceApplication` | /pp/experience/v1 |
| dvp | 18083 | `pp-dvp-root` | `com.pp.dvp.PpDvpApplication` | /pp/dvp/v1 |
| experience-issue | 18084 | `pp-experience-issue-root` | `com.pp.experienceissue.PpExperienceIssueApplication` | /pp/experience-issue/v1 |
| specialised-parts | 18085 | `pp-specialised-parts-root` | `com.pp.specialisedparts.PpSpecialisedPartsApplication` | /pp/specialised-parts/v1 |
| competitor | 18086 | `pp-competitor-root` | `com.pp.competitor.PpCompetitorApplication` | /pp/competitor/v1 |
| cmf | 18087 | `pp-cmf-root` | `com.pp.cmf.PpCMFApplication` | /pp/cmf/v1 |

⚠️ **experience 端口是 18082**（不是 18083，曾与 dvp 冲突，已改，勿改回）。

## 二、硬性要求

### 2.1 JDK 8（必须）

```powershell
# 必须用 JDK 8，不要用默认 java（JDK 17）
$java8 = "C:\Program Files\Java\jdk1.8.0_491\bin\java.exe"
& $java8 -version   # 确认 1.8.0_491
```

二期用 JDK 17 也会有问题（虽然不如一期严重，但官方要求 JDK 8，保持一致）。

### 2.2 Redis 必须 db3（已统一，无需额外操作）

二期各模块 `application-local.yml` 默认值已从 db9 改为 **db3**（2026-10-09 统一修订，与一期对齐）。dev K8s ConfigMap 设 `SPRING_REDIS_DATABASE=3`，OAuth（一期）把 token context 写在 db3，两边一致，无需环境变量覆盖。

- 改动文件（7 模块 `src/main/resources/application-local.yml` + 1 个 `pp-specialised-parts-root/src/main/java/.../config/application-local.yml` 副本）
- 同步到 `target/classes/application-local.yml`
- 验证：`Select-String application-local.yml -Pattern "SPRING_REDIS_DATABASE"` 全部显示 `:3`

**仍可用环境变量覆盖**（如需临时改回 db9 测试）：`$env:SPRING_REDIS_DATABASE = "9"`

### 2.3 pathing.jar（已就绪则跳过构建）

二期 pathing.jar 在各模块 `target/pathing.jar`。检查是否已生成：

```powershell
Get-ChildItem "C:\Users\perso\Documents\work\v-ipd\pp-powerproject-extend\pp-*-root\target\pathing.jar" | Select-Object Name, DirectoryName
```

7 个模块全有 → 跳到 §三启动。如果某模块没有，走 §2.4 构建。

### 2.4 构建 pathing.jar（依赖变了或首次）

```powershell
$mvn = "C:\Users\perso\.m2\apache-maven-3.6.3\bin\mvn.cmd"
$modDir = "<pp-powerproject-extend>\<模块>"   # 如 pp-cmf-root

# classpath
cmd /c "`"$mvn`" -f `"$modDir\pom.xml`" -s `"C:\Users\perso\.m2\settings-vipd.xml`" org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath -Dmdep.outputFile=`"$modDir\target\cp.txt`" -q"

# pathing.jar（用 New-PathingJar 函数，见 ../run-powerproject-backend/SKILL.md §1）
$depCp = (Get-Content "$modDir\target\cp.txt" -Raw).Trim() -split ";"
$entries = @("$modDir\target\classes") + ($depCp | Where-Object { $_.Trim() -ne "" })
New-PathingJar "$modDir\target\pathing.jar" $entries "$modDir\target"
```

`New-PathingJar` 函数定义见一期 SKILL §1（共用，不重复贴）。

### 2.5 同步配置到 target/classes（改配置后必须做）

jar 是旧构建打的，改完 `src/main/resources/application-local.yml` 必须复制到 target/classes：

```powershell
$modDir = "<pp-powerproject-extend>\<模块>"
Copy-Item "$modDir\src\main\resources\application-local.yml" "$modDir\target\classes\" -Force
Copy-Item "$modDir\src\main\resources\application.yml" "$modDir\target\classes\" -Force
```

## 三、启动单个服务

### 3.1 通用启动命令

```powershell
$java8 = "C:\Program Files\Java\jdk1.8.0_491\bin\java.exe"
$modDir = "C:\Users\perso\Documents\work\v-ipd\pp-powerproject-extend\<模块>"  # 如 pp-cmf-root
$mainClass = "com.pp.cmf.PpCMFApplication"  # 见 §一表

$env:SPRING_PROFILES_ACTIVE = "local"
# Redis db3 已是配置默认值，无需环境变量；需要临时覆盖时才设
# $env:SPRING_REDIS_DATABASE = "3"

cd $modDir
& $java8 -Xmx256m -Xms128m -cp "$modDir\target\pathing.jar" $mainClass *> "$modDir\target\vipd-start.log"
```

### 3.2 7 个服务的精确命令

```powershell
$java8 = "C:\Program Files\Java\jdk1.8.0_491\bin\java.exe"
$root = "C:\Users\perso\Documents\work\v-ipd\pp-powerproject-extend"
$env:SPRING_PROFILES_ACTIVE = "local"
# Redis db3 已是配置默认值（2026-10-09 修订）

# performance (18081)
& $java8 -Xmx256m -cp "$root\pp-performance-root\target\pathing.jar" com.pp.performance.PpPerformanceApplication

# experience (18082)
& $java8 -Xmx256m -cp "$root\pp-experience-root\target\pathing.jar" com.pp.experience.PpExperienceApplication

# dvp (18083)
& $java8 -Xmx256m -cp "$root\pp-dvp-root\target\pathing.jar" com.pp.dvp.PpDvpApplication

# experience-issue (18084)
& $java8 -Xmx256m -cp "$root\pp-experience-issue-root\target\pathing.jar" com.pp.experienceissue.PpExperienceIssueApplication

# specialised-parts (18085)
& $java8 -Xmx256m -cp "$root\pp-specialised-parts-root\target\pathing.jar" com.pp.specialisedparts.PpSpecialisedPartsApplication

# competitor (18086)
& $java8 -Xmx256m -cp "$root\pp-competitor-root\target\pathing.jar" com.pp.competitor.PpCompetitorApplication

# cmf (18087)
& $java8 -Xmx256m -cp "$root\pp-cmf-root\target\pathing.jar" com.pp.cmf.PpCMFApplication
```

### 3.3 后台启动 + 日志重定向（推荐）

⚠️ **不要用 `| Select-Object -First N`** —— 管道取满 N 行会关闭 stdout 管道，Java 进程被 SIGPIPE 杀掉，无声退出。

正确做法：重定向到日志文件，单独 tail：

```powershell
# 后台启动（PowerShell job 或 Start-Process）
$modDir = "$root\pp-cmf-root"
Start-Process -FilePath $java8 `
  -ArgumentList "-Xmx256m","-Xms128m","-cp","$modDir\target\pathing.jar","com.pp.cmf.PpCMFApplication" `
  -WorkingDirectory $modDir `
  -RedirectStandardOutput "$modDir\target\vipd-start.log" `
  -RedirectStandardError "$modDir\target\vipd-err.log" `
  -WindowStyle Hidden

# 看日志
Get-Content "$modDir\target\vipd-start.log" -Tail 20 -Wait
```

## 四、启动验证

```powershell
# 判断成功：日志出现
# Started PpCMFApplication in 11.379 seconds (JVM running for 11.805)

# 端口监听
netstat -ano | Select-String ":18087"   # → LISTENING

# health
curl.exe http://localhost:18087/actuator/health
# → {"status":"UP"}

# 业务接口（POST + 正确 JSON）
curl.exe -X POST http://localhost:18087/pp/cmf/v1/base-assemblies `
  -H "Content-Type: application/json" `
  -d '{"pageNum":1,"pageSize":10}'
```

启动耗时：**~11 秒**（pathing.jar 已就绪时，实测 2026-10-09 cmf 服务 11.379s）。

## 五、本地基础设施

二期服务直连 dev 共享基础设施（不走 Nacos discovery，`NACOS_DISCOVERY_ENABLED=false`）：

| 组件 | 地址 | 凭据 | 备注 |
|------|------|------|------|
| GaussDB | `jdbc:postgresql://10.82.45.158:8000,10.82.45.1:8000/PowerProject6` | `pp` / `V0y@hFre!` | 双节点主备 |
| Redis | `10.82.71.250:6379` **db3** | `cred888888` | 与一期对齐 |
| Nacos | `10.82.45.10:8848`（group `ppExploit`） | `nacos` / `V0y@hFre!` | discovery 关闭，仅 config import |
| RabbitMQ | `10.82.45.211:5672` | `admin` / `V0y@hFre!` | |
| 飞书 | app-id `cli_aa87ef669f795cd1` | （见 yml） | tenant_access_token 缓存 Redis |

环境变量全覆盖（`${VAR:default}` 模式），要覆盖任何配置直接设环境变量即可。

## 六、内存策略

- 二期 `-Xmx256m` 足够（实测 cmf 11 秒启动，内存占用 < 256MB）
- **7 个二期全启动 = ~1.8GB**（256m × 7），16GB 机器轻松
- 但 12 服务（5 一期 + 7 二期）同时启动 + 前端首编译仍会 OOM，参见一期 SKILL §0
- 登录最小集（与一期混合）：oauth(6200) + platform(6300) + business(6305) + project(6500) + 任一二期服务

## 七、常见错误速查

| 症状 | 原因 | 解决 |
|------|------|------|
| 启动后进程无声退出 | stdout 管道被 `Select-Object -First` 截断 | 用 `*> file.log` 重定向，不要用管道截断 |
| `REQUEST_408` 调一期接口失败 | Redis db 与 OAuth 不一致（db3 已是默认，若复现说明被环境变量覆盖） | 检查 `$env:SPRING_REDIS_DATABASE`；确认 target/classes 里 yml 是 `:3` |
| `找不到或无法加载主类` | pathing.jar 损坏或 manifest 有 BOM | 重新生成（见 §2.4，用 `UTF8Encoding($false)`） |
| `Port 18xxx is already in use` | 上次进程没退干净 | `Get-Process java \| Stop-Process -Force` |
| experience/dvp 端口冲突 | 两模块都配 18083 | experience 已改 18082，勿改回 |
| Nacos config is empty（WARN） | local 下 Nacos 没有对应 dataId | 正常，忽略（discovery 关闭，config 拉不到不影响启动） |
| Feign 调一期 `Load balancer does not have available server` | 二期调一期走 Nacos discovery（关闭状态） | 二期通过 integration-layer Feign + Ribbon listOfServers；确认一期服务已启动且 Ribbon 静态路由配置在 target/classes |
| `SPRING_REDIS_DATABASE` 环境变量不生效 | 改了 yml 默认值但没复制到 target/classes | `Copy-Item src\main\resources\application-local.yml target\classes\ -Force` |
| 启动慢（>60s） | 首次加载 mapper 或 Nacos 重试 | 检查日志是否在重复连 Nacos；local 下 Nacos 可达但 config 为空是正常的 |
| Quartz `Scheduler started` 后卡住 | 通常是 Quartz 初始化慢，非致命 | 等几秒看是否继续；多数会自己恢复 |

## 八、停止服务

```powershell
# 停单个（按端口找 PID）
$pid_ = (netstat -ano | Select-String ":18087" | Select-Object -First 1) -replace ".*LISTENING\s+(\d+).*", '$1'
Stop-Process -Id $pid_ -Force

# 停全部 Java
Get-Process -Name java -ErrorAction SilentlyContinue | Stop-Process -Force
```

## 九、与一期的关系（重要）

二期服务**不依赖 iform 任何代码**，但运行时通常需要调一期平台能力（OAuth 认证、组织架构、表单、消息、待办）：

| 二期要做 | 依赖 |
|---------|------|
| 用户鉴权（拿当前用户、组织） | 一期 oauth(6200) 必须启动；Redis db3 一致 |
| 调用 iform 表单/流程 | 一期 business(6305) 启动；integration-layer FormSdk |
| 发待办/消息 | 一期 platform(6300) 启动；MessageSdk/NotifySdk |
| 文件上传 | 一期 platform(6300) 的 FileSdk |

**纯二期冒烟**（不连一期）：7 个服务 + 前端，能起、能调自家接口，但调一期接口会 401/408。

**完整联调**（推荐）：5 一期 + 7 二期 + 前端，见 `../run-powerproject-backend/SKILL.md`。

## 十、来源与验证

- 2026-10-09 实测 cmf 服务（PID 37828，端口 18087 LISTENING，`Started PpCMFApplication in 10.529 seconds`）
- Redis db9 → db3 已统一修订（8 处文件，7 src + 1 java/config 副本）+ 同步 target/classes
- 7 模块 pathing.jar 全部已生成（之前构建过）
- 配置来源：各模块 `src/main/resources/application-local.yml`
- 一期启动 SKILL：`../run-powerproject-backend/SKILL.md`
