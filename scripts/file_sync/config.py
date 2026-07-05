from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 同步目标目录配置
SYNC_TARGETS = [
    {
        "name": "user_file",
        "work_dir": PROJECT_ROOT / "harness" / "knowledge" / "inputs" / "user_file",
        "user_upload": PROJECT_ROOT / "uploads" / "user_file",
    },
    {
        "name": "user_data",
        "work_dir": PROJECT_ROOT / "harness" / "knowledge" / "inputs" / "user_data",
        "user_upload": PROJECT_ROOT / "uploads" / "user_data",
    },
    {
        "name": "plan",
        "work_dir": PROJECT_ROOT / "workspace" / "plan",
        "user_upload": PROJECT_ROOT / "uploads" / "plan",
    },
    {
        "name": "LCI",
        "work_dir": PROJECT_ROOT / "workspace" / "LCI",
        "user_upload": PROJECT_ROOT / "uploads" / "LCI",
    },
]
