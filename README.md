# Cubox Exporter

一个用于导出 Cubox 收藏内容的 Python 工具。 这个项目是 cubox 如同鸡肋的开放 api 的产物。（意思是如果他们开放了更好用的 api，我也不会做这个项目了）

## Todo List

- [ ] 对搜索功能的逆向
- [ ] 对收藏功能的逆向
- [ ] 对笔记功能的逆向
- [ ] 对标签功能的逆向
- [ ] 对收藏夹功能的逆向

## 功能特点

- 自动导出 Cubox 收藏的文章和笔记
- 支持生成 Markdown 格式的导出文件
- 按日期组织导出的内容
- 保持原始文章的格式和链接

## 安装要求

- Python 3.9+
- 有效的 Cubox 账号和 API Token

## 环境配置

1. 克隆仓库：

   ```bash
   git clone https://github.com/yourusername/cubox-exporter.git
   cd cubox-exporter
   ```

2. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

3. 配置环境变量：
   创建 `.env` 文件并添加以下内容：
   ```
   CUBOX_TOKEN=your_cubox_token_here
   ```

## 使用方法

1. 确保已正确配置 `.env` 文件
2. 运行导出脚本：
   ```bash
   python cubox.py
   ```

导出的文件将保存在 `cubox_exports` 目录下，按日期命名（例如：`summary_2025-01-24.md`）。
