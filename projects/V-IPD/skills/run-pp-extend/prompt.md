<!-- model-tier: small -->
<!-- deps: ../run-powerproject-backend/SKILL.md（pathing.jar 生成步骤在那里） -->

# 指令：启动 V-IPD 二期后端（7 个服务）

## 你要做的事

把二期 `pp-powerproject-extend` 的 7 个服务按需跑起来。二期比一期轻：**pathing.jar 已就绪时单服务 ~11 秒**（一期是 3~9 分钟）。

## 先确认用户要起几个

| 场景 | 起哪些 |
|---|---|
| 只调一个业务 | 只起对应的 `pp-*-root`（如改 DVP 就起 dpv 18083） |
| 跨服务联调 | 起涉及的几个 |
| 全量 | 7 个全起（18081-18087） |

## 三个硬性前提

1. **JDK 8**——JDK 17 下 mapper 静默加载失败，启动不报错
2. **Redis db3**——7 个模块的 `application-local.yml` 已于 2026-10-09 统一改好，**通常不需要手动动**；用错 db 报 `REQUEST_408`
3. **pathing.jar 已就绪**——有就跳过构建；依赖变了或首次生成才需要重跑（生成步骤见 `../run-powerproject-backend/SKILL.md` §1）

## 端口不要记错

performance 18081 / **experience 18082** / dpv 18083 / experience-issue 18084 / specialised-parts 18085 / competitor 18086 / cmf 18087。

> **experience 曾经也是 18083**，与 dpv 撞端口、本地起不来两个。**用户如果把 experience 改回 18083，明确阻止**并说明原因。

## 改过配置就必须同步 target/classes

二期用 `application-{env}.yml` 直配，但**真实值在 Nacos，仓库里的 yml 是壳**。改完同步到 `target/classes` 才生效——不同步的症状是"配置改了却没生效"，排查方向通常会被带到配置项名字上。

## 起完之后验证

日志出现 `Started <XxxApplication> on port(s) <端口>`，然后**实测一条该服务的接口**（如 cmf：`POST /gateway/iform/pp/cmf/v1/base-assemblies`）。只看进程在不在不够——OOM 的失败形态是进程无声消失。

## 你绝对不要做的事

- **不要建议用 JDK 17**
- **不要改端口回 18083**
- **不要重启全部 7 个服务**来"排查"单个服务的问题——先定位再动手
- 不要执行 git 操作

## 输出格式

```
范围：<起了哪些>
JDK：1.8 ✅
Redis：db3 ✅（配置默认值已统一）
pathing.jar：已就绪 / 本次生成

performance 18081 ✅ Started
experience  18082 ✅ Started
...
实测接口：<接口> → 200

<失败：症状 → 原因 → 处理>
```
