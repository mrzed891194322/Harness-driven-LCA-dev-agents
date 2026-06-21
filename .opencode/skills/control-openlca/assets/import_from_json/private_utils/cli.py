def add_arguments(parser):
    """
    配置并添加用于从 JSON 导入的专用命令行参数。
    """
    parser.add_argument(
        "json_dir",
        type=str,
        help="存放 JSON 结构化配置文件的目录路径"
    )
    parser.add_argument(
        "--host", "-H",
        type=str,
        default="127.0.0.1",
        help="openLCA IPC Server 的主机地址（默认：127.0.0.1）"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="openLCA IPC Server 的端口号（默认：8080）"
    )
    parser.add_argument(
        "--project", "-P",
        type=str,
        default=None,
        help="具体工作任务/项目的名称（由 Agent 根据当前任务上下文决定）"
    )
    return parser
