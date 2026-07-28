# CLAUDE.md

## 项目概述

这是一个**纯浏览器端**的工牌/座位牌 Excel 处理工具。用户上传 Excel 文件（.xlsx/.xls），工具解析后在页面上预览数据，并支持批量生成可打印的工牌和座位牌。

## 技术架构

- **单一 HTML 文件**：所有 HTML、CSS、JS 都在 `index.html` 一个文件中
- **Excel 解析**：通过 CDN 加载 ExcelJS 库（`exceljs@4.4.0`）
- **无构建工具**：无 npm/webpack/vite，直接在浏览器中运行
- **无后端**：数据处理完全在浏览器本地完成，不上传服务器
- **样式方案**：纯 CSS（CSS 变量定义主题色），无 UI 框架

## 代码结构（index.html）

- `<style>` 块：全部 CSS 样式，使用 CSS Variables 定义主题
- `<body>` HTML：卡片式布局，包含上传区、文件信息、预览表格、设置面板、状态提示等
- `<script>` 块：全部业务逻辑
  - ExcelJS 解析上传的 Excel 文件
  - 数据提取与列识别
  - 预览表格渲染
  - 工牌/座位牌生成与打印

## 关键依赖

- **ExcelJS v4.4.0**（CDN）：`https://cdn.jsdelivr.net/npm/exceljs@4.4.0/dist/exceljs.min.js`
  - 注意：这是一个外部 CDN 依赖，离线环境下需要本地化

## 开发注意事项

- 这是一个**单文件项目**，所有修改都在 `index.html` 中
- CSS 变量定义在 `:root` 选择器中，修改主题色统一在那里改
- 没有测试框架——手动在浏览器中测试
- 兼容性目标：现代浏览器（Chrome、Edge、Firefox、Safari）
- 纯前端，不要引入 Node.js 后端依赖

## Git 仓库

- 仓库地址：`https://github.com/Banna-skech/badge-tool`
- 默认分支：`master`

## 已知问题与未来优化方向

- 目前为单文件结构，未来如果功能增多，可拆分为独立 CSS/JS 文件
- ExcelJS CDN 依赖可考虑本地化，以支持离线使用
- 可增加更多打印模板样式
