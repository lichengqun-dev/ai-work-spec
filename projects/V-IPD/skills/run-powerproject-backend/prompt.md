<!-- model-tier: small -->
<!-- deps: SKILL.md（本篇是操作手册，细节全在 SKILL.md） -->

# 指令：启动 V-IPD 完整本地开发环境

## 你要做的事

把「一期 5 服务 + 二期 7 服务 + 前端」在本地跑起来。**逐步照 SKILL.md 做，不要跳步。**

## 先问清楚用户要哪种范围

| 用户想干什么 | 起哪些 |
|---|---|
| 只调前端页面 | 前端 + 需要的少数后端（前端 proxy 有兜底，不一定要全起） |
| 调一期业务 | 前端 + oauth 6200 + platform 6300 + business 6305 + project 6500 |
| 调二期业务 | 前端 + 对应 `pp-*-root`（18081-18087）+ integration-layer 可达的一期服务 |
| 全量联调 | 12 个服务 + 前端，**先看内存策略再动手** |

**「登录最小集」是 oauth + platform + business + project 四个**，少一个都可能登录失败。

## 动手前的三个必须先确认

1. **JDK 是 8**，不是默认的 17。JDK 17 下 mapper 会**静默加载失败**，启动不报错、调用时才炸
2. **内存够不够**：16GB 机器上 12 服务 × 默认 4GB 堆必挂，**必须先定 `-Xmx`**（一期 512m / 二期 256m）
3. **Redis 是 db3**：用错 db 报 `REQUEST_408`，而错误信息完全没提 db 编号

## 顺序（关键，顺序错了会白等）

后端依赖变过 → 先 `mvn install`（全量 ~6 分钟，只需一次）；然后每模块生成 classpath + pathing.jar；
**配置同步到 `target/classes`**；最后才起服务。前端首编译要几分钟 + ~4GB，**别和后端同时来**。

## 起完之后必须验证，不能只看"进程还在"

- 一期：日志出现 `Started <XxxApplication> on port(s) <端口>`
- 二期：同上
- 前端：`http://localhost:9528/` 返回 200，然后**实测一条一期接口和一条二期接口**
- 登录：`/gateway/iform/oauth2/v3/user/captcha` 返回 200（不是「非法请求」6010101）

**只看进程在不在是不够的**——OOM 的失败形态就是进程无声消失，而 mapper 加载失败要调用到才暴露。

## 常见失败怎么报

SKILL.md 有「常见错误速查」。用户报症状时**先对号**再给建议：

| 症状 | 九成是这个 |
|---|---|
| 进程无声挂掉 | OOM，没加 `-Xmx` |
| 登录报「非法请求」6010101 | GatewayFilter 没关，或改了配置没同步 target/classes |
| `REQUEST_408` | Redis 不是 db3 |
| `Mapped Statements collection does not contain value` | 用了 JDK 17，或删了 `dataSource-platform-local.xml` |
| `找不到或无法加载主类` | pathing.jar 有 BOM，或目录条目没以 `/` 结尾 |
| `Load balancer does not have available server` | Nacos discovery 关了但没配 Ribbon `listOfServers` |

## 你绝对不要做的事

- **不要为了"跑起来"改动 `vuve.config.js` / 共享配置去绕过问题**——那些配置是刻意配好的，症状另有原因
- **不要建议用 JDK 17**，即使报错看起来和 JDK 无关
- **不要擅自杀掉用户的 Java 进程**（`Stop-Process -Force`）——先说清楚要杀哪些
- 不要执行 git 操作

## 输出格式

```
范围：<起了哪些服务>
JDK：1.8 ✅ / ❌（若是 17，停在这里先换）
内存：一期 -Xmx512m / 二期 -Xmx256m / 前端 NODE_OPTIONS=...
启动结果：
  一期 oauth 6200   ✅ Started
  一期 platform 6300 ✅
  ...
  前端 9528         ✅ 200
验证：登录接口 200 / 一期接口 200 / 二期接口 200

<如有失败：症状 → 原因 → 处理，逐条>
```
