<!-- model-tier: small -->
<!-- deps: SKILL.md（代理矩阵与常见坑全在那里） -->

# 指令：启动 V-IPD 前端（Vue 2.6，端口 9528）

## 你要做的事

在本地把 `powerprojectforjava-frontend` 跑起来，并保证它连到**正确的后端**。

## 一、先设环境变量，再启动

```
NODE_OPTIONS = "--openssl-legacy-provider --max-old-space-size=8096"
```

**两个都不能省**：
- 少了 `--openssl-legacy-provider` → Node 17+ 报 `digital envelope routines::unsupported`（webpack 老 loader 用了 OpenSSL 3 废弃的 MD4）
- 少了堆上限 → 首编译 OOM（21000+ 模块需几分钟 + ~4GB）

## 二、内存策略先讲清楚（16GB 机器）

**别和后端 12 个服务同时来。** 内存不足时**先停 Java**，等前端编译完（`http://localhost:9528/` 返回 200）再起后端。

## 三、启动后第一件事：确认接口打到哪

前端 `npm run dev` 打开页面**不等于**本机起了后端。请求打到哪看 `vue.config.js` 的 `devServer.proxy`：

| 前缀 | 去向 |
|---|---|
| `^/gateway/iform/<alias>/v3` | 一期本地（剥掉整个前缀） |
| `^/gateway/iform/pp/<alias>/v1` | 二期本地（只剥 `/gateway/iform`，服务自带前缀） |
| `^/gateway`（兜底） | `https://core-test.voyah.cn` —— **环境上的旧代码** |
| `^/api` | e签宝 |
| `^/dhtmlx` | core-test（甘特导出） |

> **排查接口问题的第一步永远是确认这一层。** "页面能打开但数据不对"，九成是兜底代理把请求送到了 core-test，而不是本机后端。

## 四、验证

`http://localhost:9528/` 返回 200，然后**分别实测一条一期接口和一条二期接口**走通。

## 你绝对不要做的事

- **不要改 `vue.config.js` 的 proxy 去"修"一个看起来不通的接口**——那套代理是刻意配好的，先确认请求该走哪
- **不要建议升级 Vue 3**（本项目明确不升）
- **不要顺手跑 `pnpm run build`**（5m14s，且不带宽堆参数会 OOM）；要构建时按 SKILL.md §六 加参数
- 不要执行 git 操作

## 输出格式

```
NODE_OPTIONS：--openssl-legacy-provider --max-old-space-size=8096 ✅
编译：完成（~N 分钟）
入口：http://localhost:9528/ → 200
代理实测：
  一期 /gateway/iform/pp-project/v3/api/... → 200
  二期 /gateway/iform/pp/cmf/v1/...        → 200
兜底提示：未命中本地服务的请求会走 core-test（环境上的旧代码）

<失败：症状 → 原因 → 处理>
```
