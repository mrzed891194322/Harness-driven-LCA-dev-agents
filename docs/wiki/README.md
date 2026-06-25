# Wiki 目录结构与维护说明

本目录是当前项目的 Git Wiki 仓库本地副本，用于存放项目的 Wiki 文档与相关静态资产。

## 📁 目录架构说明

```text
wiki/
├── _Sidebar.md             # Wiki 侧边栏导航配置文件
├── Home.md                 # Wiki 默认首页
├── env_setup.md            # 环境安装与配置指南
├── project_prep.md         # 项目准备工作指南
├── rag_guide.md            # RAG 知识库使用指南
├── agent_skill_guide.md    # 智能体技能编写规范
├── README.md               # 本维护说明文档
└── assets/                 # Wiki 资产目录
    ├── images/             # 存放 Markdown 中引用的图片资源
    │   └── project_prep/   # 项目准备相关的配图
    │       ├── openlca-ipc.png
    │       └── openlca-ipc-cn.png
    └── scripts/            # 维护脚本目录
        └── push_wiki.py    # Git 一键更新与推送脚本
```

---

## 🚀 自动推送脚本使用指南

当您修改或添加了 Wiki 文档、图片后，可以在 `wiki` 根目录下使用以下 Python 指令来一键暂存、提交并推送更改至远程 Wiki 仓库：

### 1. 使用默认提交信息（按当前时间命名）
```bash
uv run python assets/scripts/push_wiki.py
```

### 2. 使用自定义提交信息
```bash
uv run python assets/scripts/push_wiki.py "您的自定义提交说明"
```
