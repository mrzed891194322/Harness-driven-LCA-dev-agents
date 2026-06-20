def add_arguments(parser):
    """
    配置并添加用于获取模型图信息的命令行参数。
    """
    parser.add_argument(
        "system",
        type=str,
        help="目标产品系统 (Product System) 的名称或 UUID"
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
        "--output", "-o",
        type=str,
        default=None,
        help="可选，将图结构以 JSON 连线信息导出到指定文件路径"
    )
    return parser
