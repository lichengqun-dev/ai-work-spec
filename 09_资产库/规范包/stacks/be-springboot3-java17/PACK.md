---
pack: be-springboot3-java17
prefix: STD-SB3
dimension: be
key: be
version: 0.1.0
title: Java 17/21 + Spring Boot 3 后端栈
applies_when: 项目后端使用 Java 17 或 21 + Spring Boot 3.x
owner: 待指定
updated: 2026-10-19
status: partial
files:
  - 编码规范.md
---

# be-springboot3-java17

## 实测技术栈

| 组件 | 版本 |
|---|---|
| Java | 17 或 21（两个版本并存） |
| Spring Boot | 3.x |
| 数据库 | 达梦 DM8（见 db-dm8 包） |

## 这个包要解决什么

新项目主力栈。**注意 Java 17 与 21 并存**：21 引入了虚拟线程与更完整的模式匹配，但跨项目复用的代码必须以 **17 为下限**，否则复制到 17 项目即编译失败。

与 `be-springboot2-java8` 的差异不只是语言版本，还包括 `javax.*` → `jakarta.*` 的命名空间迁移。

## 条目文件

| 文件 | 内容 |
|---|---|
| [编码规范.md](./编码规范.md) | 本包条目 |

## 待补充清单

- [ ] 分层架构与包结构约定
- [ ] 统一响应封装与异常处理
- [ ] 事务边界与传播行为
- [ ] 虚拟线程（Java 21）的适用与禁用场景
- [ ] 与 be-springboot2-java8 的差异清单（迁移参考）

> 条目按"真实批次反推"的顺序补充，不要一次性凭空写完。
