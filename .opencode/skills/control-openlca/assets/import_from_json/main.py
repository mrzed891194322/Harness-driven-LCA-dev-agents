import sys
import argparse
from pathlib import Path

# 确保在 Windows GBK 环境下能够正常输出 Unicode 字符而不报错
# --user 环境配置是否可以复用？
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# 将 assets 目录加入 sys.path 以使用公共的 utils
sys.path.append(str(Path(__file__).parent.parent))
# 将当前脚本目录加入 sys.path 以使用私有的 private_utils
sys.path.append(str(Path(__file__).parent))

try:
    import olca_schema
except ImportError:
    print("Error: Required package 'olca-schema' is not installed.")
    sys.exit(1)

# 从共享的 utils 导入
from utils.connection import connect_ipc

# 从私有的 private_utils 导入
from private_utils.cli import add_arguments
from private_utils.importer import import_json_files

def main():
    parser = argparse.ArgumentParser(
        description="连接 openLCA IPC Server 并读取结构化 JSON 文件将其导入到数据库中。"
    )
    add_arguments(parser)
    args = parser.parse_args()

    # 1. 连接 IPC Server
    client = connect_ipc(args.host, args.port, olca_schema.Flow)

    # 2. 导入指定文件夹中的 JSON 文件
    import_json_files(client, Path(args.json_dir), project_name=args.project)

if __name__ == "__main__":
    main()
