---
name: replicate-from-uat
description: 一比一复刻现系统（UAT）页面的标准工作流。重构任何 V-IPD 页面前必读：源码定位 + UAT 实测 + 双向互证 + 实现 + 视觉找茬验证 + 记录。适用于前端页面复刻、后端接口行为对齐两类任务。
---

# 一比一复刻现系统页面（replicate-from-uat）

> 前提共识：本次重构是"去低码 + 服务聚合"，**前端 UI/UE 与现系统保持一致是硬性要求**。
> 铁律：**不许只看页面不读代码，也不许只读代码不看页面**——两者互证才能保证一比一。

## 适用场景

- 重构（Vue3 复刻）现系统的任意页面/组件
- 对齐现系统的后端接口行为（分页/校验/错误码语义）

## 工作流（六步，缺一不可）

### 第 1 步：源码定位（先读老代码）

老前端仓库：`C:\Users\perso\Documents\work\v-ipd\powerprojectforjava-frontend`（Vue2 + Element UI）
老后端仓库：`C:\Users\perso\Documents\work\v-ipd\powerprojectforjava-backend`（一期）、`pp-powerproject-extend`（二期）

1. 按 URL 找页面：菜单 `default_url_`（查 `migration/tools/core_menu_final.json` 或 `menu_tree.txt`）→ 前端 `src/router/routes.js` + `src/router/utils.js`（`/d/ /dk/ /f/` 前缀是数据模板/表单渲染入口，其余按 views 路径）
2. 读页面 SFC：template 结构（class 命名要照抄，如登录页的 `.login-border/.login-main`）+ 引入的 SCSS（如 `@/assets/styles/pages/xxx.scss` 必须连样式文件一起读）
3. 读老后端对应 Provider/Controller：接口路径、入参出参包装、分页方式、状态值语义
4. 涉及动态表单/数据模板的页面：查 `migration/tools/data_templates.txt`、`bo_table_map.txt`（模板 key → BO → 物理表）

### 第 2 步：UAT 实测（再看真实页面）

UAT：`https://core-test.voyah.cn/`（账号 pms/123456；**只读，禁止增删改数据**；UAT 偶发服务不可用，先刷新重试）

1. **DOM 结构**：浏览器 domSnapshot，拿到可访问性树（元素层级/role/name）
2. **计算样式**（比截图更精确）：`getComputedStyle` 逐元素提取关键属性——布局（宽高/定位/padding/margin）、颜色、字体、圆角、阴影、层级。样例代码：

```js
const cs = (el, props) => Object.fromEntries(props.map(p => [p, getComputedStyle(el).getPropertyValue(p)]));
cs(document.querySelector('.login-border'), ['width','min-height','background-color','border-radius','box-shadow','padding'])
```

3. **静态资源**：背景图/logo 用 curl 从 UAT 接口下载入库（如登录背景 `getSystemImage?imageType=LoginBackground`）
4. **截图**：同视口尺寸截图存档，供第 5 步对比

### 第 3 步：双向互证

- 源码值 vs 运行值不一致时（主题/全局样式覆盖）：**以运行值为准**，但要在代码注释里注明源码出处（如 `login.scss` 定义 vs 主题覆盖后的实际值）
- 找不到样式来源时回读第 1 步的 SCSS import 链（主题文件 `assets/styles/theme/pp/`）

### 第 4 步：实现

1. **结构照抄**老代码的 class 层级（`.login-border > .login-main > h3 + form`），便于样式逐项映射
2. 样式逐项对齐第 2 步提取的计算值
3. **Element Plus 与 Element UI 的已知差异必须主动覆盖**（见下方对照表）
4. 交互对齐：回车提交/记住账号/加载态/错误提示位置

#### Element UI → Element Plus 差异对照表（复刻必查）

| 差异点 | Element UI（现系统） | Element Plus（须覆盖） |
|--------|---------------------|------------------------|
| 占位符颜色 | `#C0C4CC` | 默认 `#A8ABB2` 偏深 → 全局 `--el-text-color-placeholder: #c0c4cc` |
| 字体栈 | 系统栈（-apple-system/Segoe UI…） | 自定义栈 → 全局 body 对齐 UAT 实测值 |
| 输入框边框 | border 0.67px #DCDFE6 | box-shadow 实现 → `box-shadow: 0 0 0 0.67px #DCDFE6 inset` |
| checkbox 字重 | 400 | 默认 500 → 显式 400 |
| 表单 label | 顶置需手写 form-item 拆行（标签行+输入行，间距 2px/10px 奇偶规则） | 同结构可实现 |
| 事件绑定 | `@keyup.enter.native` | 直接 `@keyup.enter`（EP 透传） |
| **图标体系** | `iform-icons` 字体（`src/assets/fonts/iconfont.*`，如 eye=`\e77b`/eye-slash=`\e77c`）；语言图标为内联 SVG | **字体文件直接拷贝复用**（已入库 `src/assets/fonts/` + `styles/iform-icons.scss`）；SVG 图标从 UAT DOM 抓 `outerHTML` 存组件（如 `components/TranslateIcon.vue`）。注意：EP 默认图标形状不同，禁止用 EP 图标替代现系统图标 |
| 按钮文字 | span 16px/500（按钮本身 font-size 14） | EP 无内层 span 尺寸 → 自定义 `.submit-text` 或显式覆盖 |
| 图标行高偏移 | `i` 图标 24px 精确定位 | EP dropdown/input suffix 默认行高会顶偏 → 容器 `line-height: 0` 修正 |

**几何验证法（比截图 diff 更精确）**：两边分别 `getBoundingClientRect()` 提取卡片内元素相对坐标（x,y,w,h），逐项对比到像素级。UAT 登录卡片基准锚点：card 420×406 / h3(46,50,328,39) / lang(381,10,24,24) / label(46,115) / input(46,143,328,38) / eye(344,225,25,38) / submitText(194,326,32)。

### 第 5 步：验证

1. **同视口截图对比**：本地页与 UAT 页同尺寸截图，交视觉模型"找茬式"对比（prompt 要求列出最细微差异：字重/间距/颜色/渲染）
2. **交互回归**：登录/提交/跳转/记住态全流程跑一遍
3. 发现差异回到第 4 步修，直到视觉模型逐项判"一致"

### 第 6 步：记录

- `docs/重构日志.md` 追加一条：页面名、对齐的样式要点、发现的 EP 差异、验证结果
- 复刻过程中沉淀的新差异点补充进上方对照表（本 skill 是活文档）

## 安全红线

- 登录密码等敏感字段**禁止明文传输**（现行方案：前端 jsencrypt + RSA 公钥，公钥接口 `/api/v1/auth/public-key`）
- UAT 只读：禁止创建/修改/删除任何数据；退出登录等会话操作允许

## 常用工具速查

- 只读查库：`migration/tools/QueryDB.java`（`java -cp opengauss-jdbc-5.1.0.jar QueryDB.java "SQL"`，UAT 库连接见文件默认值）
- 菜单/模板映射：`migration/tools/core_menu_final.json`、`data_templates.txt`、`bo_table_map.txt`、`menu_tree.txt`
- 视觉对比：两边同视口截图 + 视觉模型逐项对比（9 要点清单式 prompt）
