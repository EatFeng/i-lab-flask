# 实验室指挥讲解管理平台

这是一个基于 Flask 的 Web 应用程序，用于管理实验室信息和相关的讲解内容。该平台支持添加、更新、删除实验室信息，以及为每个实验室创建和管理讲解内容。

## 功能

- **实验室管理**：可以查看、添加、更新和删除实验室。
- **讲解内容管理**：为每个实验室添加讲解内容，包括文本、生成音频和相关操作。
- **音频生成**：支持将讲解内容转换为音频文件。
- **数据存储**：使用 MySQL 作为后端数据库存储实验室和讲解内容信息。

## 技术栈

- **前端**：HTML, CSS, JavaScript
- **后端**：Python, Flask
- **数据库**：MySQL
- **音频处理**：PaddleSpeech

## 运行环境

- Python 3.6+
- Flask 1.1.2+
- Flask-SQLAlchemy 2.4.4+
- Flask-Migrate 2.7.0+
- PaddleSpeech

## 安装指南

1. **克隆项目**：

```bash
git clone https://github.com/yourusername/lab-management-system.git
cd lab-management-system
```

2. **创建conda环境**：

```bash
conda env create -f environment.yml
```

3. **激活环境**：

```bash
conda activate i-lab-flask
```

4. **数据库配置**：

确保你的 MySQL 服务正在运行，并创建一个数据库 `flaskappdb`。修改 `app.py` 中的数据库连接配置，如果需要的话。

5. **运行应用**：

```bash
flask run
```

或者直接运行：

```bash
python app.py
```

## 使用说明

- 访问 `http://127.0.0.1:5000/manage` 来管理实验室。
- 访问 `http://127.0.0.1:5000/lab/<lab_id>` 来管理特定实验室的讲解内容。
- 使用 `http://127.0.0.1:5000/new-lab` 添加新的实验室。

## 目录结构

```
lab-management-system/
│
├── app.py  # 主应用文件
├── templates/
│   ├── home.html
│   ├── manage.html
│   ├── lab.html
│   └── new_lab.html
│
├── static/
│   ├── output/  # 音频文件输出目录
│   └── styles.css  # 样式文件
│
└── migrations/  # 数据库迁移文件
```

## 贡献

欢迎提交 Pull Request 或创建 Issue。

## 许可证

本项目采用 [MIT 许可证](LICENSE)。
