---
name: run-frontend
description: 在本地启动 V-IPD 前端 powerprojectforjava-frontend（Vue 2.6，端口 9528）并理解其代理矩阵：/gateway/iform/* 按服务拆分到本机 12 个后端、兜底 core-dev、/api 走 e签宝。涵盖 Node 24 openssl legacy、内存策略、首次编译、包管理器、常见坑。当用户要求启动前端、排查代理转发、本地连后端时使用。
---

# V-IPD 前端本地启动（powerprojectforjava-frontend）

> 后端启动见 `../run-powerproject-backend/SKILL.md`（一期）与 `../run-pp-extend/SKILL.md`（二期）。
> 前后端联调整体流程见 `../debug-full-stack/SKILL.md`。

## 一、基本信息

| 项 | 值 |
|----|-----|
| 技术栈 | Vue 2.6.14 + Vue CLI 5.0.8（Webpack 5.90.3） |
| dev server | `host: 0.0.0.0`，端口 **9528**，访问 `http://localhost:9528/` |
| 首次编译 | 21000+ 模块，几分钟 + **~4GB 内存** |
| 请求基址 | `.env.development` 里 `VUE_APP_BASE_API = '/gateway/iform'`（相对路径走 devServer 代理，浏览器不跨域） |

## 二、启动步骤

### 2.1 前置

- Node 24（或其他 17+ 版本）已装
- 依赖已安装（`node_modules` 存在）；没有则 `pnpm install`（约 2 分钟）

### 2.2 启动（推荐）

```powershell
cd "C:\Users\perso\Documents\work\v-ipd\powerprojectforjava-frontend"
$env:NODE_OPTIONS = "--openssl-legacy-provider --max-old-space-size=8096"
node "node_modules/@vue/cli-service/bin/vue-cli-service.js" serve --open
```

或用 package.json 脚本：

```powershell
pnpm run dev2   # 脚本内已带 NODE_OPTIONS=--openssl-legacy-provider（export 版）
```

### 2.3 判断成功

- 终端出现 `App running at: - Local: http://localhost:9528/`
- `curl http://localhost:9528/` 返回 200
- **编译中 HTTP 000 是正常的**（21000+ 模块要编译几分钟），等 200

## 三、代理矩阵（vue.config.js devServer.proxy，已配置勿动）

### 3.1 一期 5 服务：剥掉整个前缀（等价网关 StripPrefix=3）

| 匹配 | 转发到 | pathRewrite |
|------|--------|-------------|
| `^/gateway/iform/platform/v3` | `http://localhost:6300` | 剥掉整个匹配前缀 |
| `^/gateway/iform/business/v3` | `http://localhost:6305` | 同上 |
| `^/gateway/iform/oauth2/v3` | `http://localhost:6200` | 同上 |
| `^/gateway/iform/pp-project/v3` | `http://localhost:6500` | 同上 |
| `^/gateway/iform/pp-document/v3` | `http://localhost:6400` | 同上 |

### 3.2 二期 7 服务：只剥 `/gateway/iform`（服务自带 `/pp/<alias>/v1` 前缀）

| 匹配 | 转发到 |
|------|--------|
| `^/gateway/iform/pp/cmf/v1` | `http://localhost:18087` |
| `^/gateway/iform/pp/dvp/v1` | `http://localhost:18083` |
| `^/gateway/iform/pp/performance/v1` | `http://localhost:18081` |
| `^/gateway/iform/pp/experience/v1` | `http://localhost:18082` |
| `^/gateway/iform/pp/experience-issue/v1` | `http://localhost:18084` |
| `^/gateway/iform/pp/specialised-parts/v1` | `http://localhost:18085` |
| `^/gateway/iform/pp/competitor/v1` | `http://localhost:18086` |

### 3.3 兜底与第三方

| 匹配 | 转发到 | 说明 |
|------|--------|------|
| `^/gateway`（未匹配上面的） | `http://core-dev.voyah.cn` | **不想本地启动的服务自动走 dev 环境**（如报表）。用法：注释掉对应的 localhost 规则即可 |
| `^/dhtmlx` | `http://core-dev.voyah.cn` | 甘特导出走 dev |
| `^/api` | `https://esignoss.esign.cn/` | e签宝（电子签名），**不是主后端** |

### 3.4 排查接口问题的第一步

先确认请求走的哪个代理：浏览器 DevTools Network 里看 URL 前缀。`/api/xxx` 打到 esign 是**预期行为**不是 bug；没起本地后端的服务走 `^/gateway` 兜底到 core-dev。

## 四、包管理器

- `package.json#packageManager` 声明 `yarn@1.22.21`，但 Node 24 下 yarn 1 报版本错
- 仓库无锁文件进 git；本地推荐 **pnpm** + 根目录 `.npmrc`（**不要提交**）：
  ```
  package-manager-strict=false
  shamefully-hoist=true
  strict-peer-dependencies=false
  auto-install-peers=true
  ```
- **不要提交** `.npmrc` 和 `pnpm-lock.yaml`

## 五、内存策略（16GB 机器必读）

- 首次编译需要 **~4GB**（`--max-old-space-size=8096`）
- **不要 12 个 Java 服务 + 前端首编译同时跑**（OOM 全挂）
- 内存不足：先停 Java（`Get-Process java | Stop-Process -Force`），等前端编译完（9528 返回 200）再起 Java
- 之后再起 Java 时一期 `-Xmx512m`、二期 `-Xmx256m`

## 六、构建（生产）

```powershell
$env:NODE_OPTIONS = "--openssl-legacy-provider --max-old-space-size=8192"
node "node_modules/@vue/cli-service/bin/vue-cli-service.js" build --mode prod.cloud
# 已验证 5m14s；chunk-vendor.js 6.5MB 偏大，优化跑 build -- --report
```

多环境 `.env`：`.env.development` / `.env.staging` / `.env.production` / `.env.prod.test` / `.env.prod.boot` / `.env.prod.cloud`，对应 scripts `build:stage` / `build:prod:test` / `build:prod:boot` / `build:prod:cloud`（测试云/私有化/公有云多套交付目标）。

## 七、常见坑

| 症状 | 原因 | 解决 |
|------|------|------|
| `digital envelope routines::unsupported` | Node 17+，webpack 老 loader 用了 OpenSSL 3 废弃的 MD4 | `--openssl-legacy-provider` |
| `pnpm run build` OOM exit 134 | V8 默认堆 ~1.7GB 不够 | `--max-old-space-size=8192` |
| 编译中 HTTP 000 / 超时 | 21000+ 模块在编译，或内存被 Java 占满 | 等；必要时先停 Java |
| dev 启动刷 400+ ESLint error | 历史债 406 个 | `lintOnSave` 已降 warning 不阻塞，看到满屏红字别慌，等 `App running at:` |
| `pnpm run lint` 大面积改动 | 默认带 `--fix` | 慎跑；局部修用 `npx eslint --fix <file>` |
| 页面 404 但 Console 无报错 | 菜单 `defaultUrl` 带 `.vue` 后缀，require 失败被 catch 吞掉 | 菜单 URL 不带 `.vue` 后缀 |
| 接口打到 esign | `^/api` 前缀被代理到 e签宝 | 预期行为；主后端走 `/gateway/iform` |
| 接口打到 core-dev | 本地没起对应服务，走兜底 | 起本地服务或确认这是预期 |
| 端口 9528 被占 | 上次 dev server 没退 | `Get-Process node | Stop-Process -Force` |

## 八、subpage 双入口

`src/main.js`（主应用 index.html）与 `src/subpage/main.js`（subpage.html 子页面）是两个独立入口，subpage 有独立 router/store/views。**改 `src/business/` 或共用组件时确认是否要两边同步**。

## 九、验证清单

```powershell
# 页面
curl http://localhost:9528/    # → 200

# 一期登录链路（本地后端已起时）
curl.exe http://localhost:9528/gateway/iform/oauth2/v3/user/captcha -X POST    # → 200

# 二期（本地后端已起时）
curl.exe http://localhost:9528/gateway/iform/pp/cmf/v1/base-assemblies -X POST -H "Content-Type: application/json" -d "{\"pageNum\":1,\"pageSize\":10}"
```
