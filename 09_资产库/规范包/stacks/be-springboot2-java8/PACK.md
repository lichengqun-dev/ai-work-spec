---
pack: be-springboot2-java8
prefix: STD-SB2
dimension: be
key: be
version: 0.1.0
title: Java 8 + Spring Boot 2.6 后端栈
applies_when: 项目后端使用 Java 8 + Spring Boot 2.6.x + Spring Cloud Alibaba
owner: 待指定
updated: 2026-10-19
status: partial
files:
  - 编码规范.md
---

# be-springboot2-java8

## 实测技术栈

| 组件 | 版本 |
|---|---|
| Java | 1.8 |
| Spring Boot | 2.6.13 |
| Spring Cloud | 2021.0.5 |
| Spring Cloud Alibaba | 2021.0.5.0 |
| 数据库 | 达梦 DM8（见 db-dm8 包） |

## 这个包要解决什么

**为什么 Java 8 需要单独一个包**：AI 生成代码时默认会写现代语法（`var`、`record`、文本块、`switch` 表达式、`Stream.toList()`），这些在 Java 8 下**编译期直接失败**。这不是风格偏好，是编译能否通过的问题。同理 Spring Boot 2.6 用 `javax.*` 而 3.x 用 `jakarta.*`，混用同样编译失败。

本包存在的首要理由就是拦住这两类返工。

## 条目文件

| 文件 | 内容 |
|---|---|
| [编码规范.md](./编码规范.md) | 本包条目 |

## 待补充清单

- [ ] 分层架构与包结构约定
- [ ] 异常处理与统一响应封装
- [ ] 事务边界与传播行为
- [ ] 日志规范（traceId 透传）
- [ ] 与存量模块的依赖方向约束

> 条目按"真实批次反推"的顺序补充，不要一次性凭空写完。
