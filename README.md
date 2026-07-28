# 工牌/座位牌 Excel 处理工具

纯浏览器端 Excel 处理工具，无需后端服务器，上传 Excel 即可批量生成工牌和座位牌。

## 功能

- 📤 上传 Excel 文件（.xlsx / .xls）
- 👁️ 预览表格数据，自动识别相关列
- 🖨️ 批量生成工牌和座位牌，支持打印
- 🔒 数据完全在浏览器本地处理，不会上传到任何服务器

## 使用方法

1. 打开 `index.html`（直接双击或用浏览器打开）
2. 上传包含员工信息的 Excel 文件
3. 预览数据、调整设置
4. 一键生成并打印

## 技术栈

- 纯 HTML/CSS/JavaScript（无框架依赖）
- [ExcelJS](https://github.com/exceljs/exceljs)（CDN 加载，用于解析 Excel）
- 零构建、零依赖安装，开箱即用

## 项目结构

```
badge-tool/
├── index.html    # 主页面，包含全部逻辑
├── README.md     # 项目说明
├── CLAUDE.md     # AI 辅助开发指引
└── .gitignore    # Git 忽略规则
```

## 本地运行

无需安装任何依赖，直接用浏览器打开 `index.html` 即可。

也可以使用任意静态文件服务器：

```bash
# Python 3
python -m http.server 8080

# Node.js (npx)
npx serve .
```

## License

MIT
