def add_arguments(parser):
    """
    配置并添加用于计算产品系统的专用命令行参数。
    """
    parser.add_argument(
        "system",
        type=str,
        help="目标产品系统 (Product System) 的名称或 UUID"
    )
    parser.add_argument(
        "--method", "-m",
        type=str,
        default=None,
        help="可选，生命周期影响评估方法 (LCIA Method) 的名称或 UUID"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="openLCA IPC Server 的端口号（默认：8080）"
    )
    parser.add_argument(
        "--host", "-H",
        type=str,
        default="127.0.0.1",
        help="openLCA IPC Server 的主机地址（默认：127.0.0.1）"
    )
    parser.add_argument(
        "--amount", "-a",
        type=float,
        default=1.0,
        help="计算所需的功能单位数量（默认：1.0）"
    )
    parser.add_argument(
        "--allocation", "-al",
        type=str,
        default=None,
        help="分配方法选择 (physical, economic, causal, none, default)"
    )
    parser.add_argument(
        "--regionalized", "-r",
        action="store_true",
        help="启用区域化计算"
    )
    parser.add_argument(
        "--costs", "-c",
        action="store_true",
        help="启用成本核算"
    )
    parser.add_argument(
        "--parameter", "-param",
        action="append",
        default=[],
        help="重定义计算参数的值（格式：参数名=数值，支持多次指定，例如 -param p1=1.5 -param p2=2.0）"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="计算结果导出的文件路径（支持 .json 或 .csv 格式）"
    )
    return parser
