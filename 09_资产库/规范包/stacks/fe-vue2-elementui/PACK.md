---
pack: fe-vue2-elementui
prefix: STD-VUE2
dimension: fe
key: fe
version: 0.1.0
title: Vue 2.6 + Element UI 前端栈
applies_when: 项目前端使用 Vue 2.6 + Element UI 2.x（存量栈）
owner: 待指定
updated: 2026-10-19
status: skeleton
files:
  - 编码规范.md
---

# fe-vue2-elementui

## 实测技术栈

| 组件 | 版本 |
|---|---|
| Vue | 2.6.14 |
| Element UI | 2.15.14 |
| ant-design-vue | 1.7.8 |
| @vue/composition-api | 1.7.2 |
| axios | ^1.7.3 |

## 这个包要解决什么

这是**存量栈**，不是新选型。规范目标不是"写得更现代"，而是**防止它在维护过程中被改坏**——尤其要拦住"顺手升级到 Vue 3"这类改动，它会牵动整个前端，必须走独立批次评估。

项目内同时存在 Element UI 与 ant-design-vue 两套 UI 库。本包不主张移除（收敛成本过高），但要求同类组件在同一页面内不得混用。

## 条目文件

| 文件 | 内容 |
|---|---|
| [编码规范.md](./编码规范.md) | 本包条目 |

## 待补充清单

- [ ] 状态管理约定（Vuex 模块划分、命名空间）
- [ ] 路由与权限约定
- [ ] 构建与打包配置
- [ ] 常见陷阱（从历史缺陷中提炼）

> 条目按"真实批次反推"的顺序补充，不要一次性凭空写完。
