---
pack: fe-react-antd
prefix: STD-REACT
dimension: fe
key: fe
version: 0.1.0
title: React 18 + antd 5 + Vite 前端栈
applies_when: 项目前端使用 React 18 + antd 5
owner: 待指定
updated: 2026-10-19
status: skeleton
files:
  - 编码规范.md
---

# fe-react-antd

## 实测技术栈

| 组件 | 版本 |
|---|---|
| React / react-dom | ^18.3.1 |
| antd | ^5.20.0 |
| react-router-dom | ^6.26.0 |
| Vite | ^5.3.4 |
| @xyflow/react | ^12.11.3 |

## 这个包要解决什么

React 项目专用。核心关注点是**服务端状态与客户端状态的分离**——把接口数据塞进全局 store 是 React 项目最常见的状态管理债务。

## 条目文件

| 文件 | 内容 |
|---|---|
| [编码规范.md](./编码规范.md) | 本包条目 |

## 待补充清单

- [ ] 目录组织与模块划分约定
- [ ] 服务端状态管理方案（是否引入 TanStack Query）
- [ ] 流式接口（SSE）的对接约定
- [ ] 画布类组件的规范
- [ ] 组件测试约定

> 条目按"真实批次反推"的顺序补充，不要一次性凭空写完。
