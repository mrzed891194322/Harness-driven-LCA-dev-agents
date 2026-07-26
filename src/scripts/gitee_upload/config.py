# -*- coding: utf-8 -*-

from pathlib import Path

# 项目根目录
PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)

# Git 远程仓库名称，默认为 'gitee'
GIT_REMOTE_NAME = "gitee"

# 默认的 Gitee 仓库 URL，当本地未添加该远程源时可用于自动添加
DEFAULT_GITEE_URL = "https://gitee.com/mrzed891194322/multi-agent-lca-orchestrator.git"
