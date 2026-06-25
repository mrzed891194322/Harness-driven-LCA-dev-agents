import argparse

def add_arguments(parser: argparse.ArgumentParser):
    """添加专门用于 query_descriptors 的命令行参数"""
    parser.add_argument(
        "type",
        type=str,
        choices=[
            "Process", "Flow", "ProductSystem", "ImpactMethod",
            "FlowProperty", "UnitGroup", "Actor", "Source",
            "Project", "Location", "Currency", "SocialIndicator"
        ],
        help="Entity type to query"
    )
    parser.add_argument("--search", type=str, default="", help="Search string to filter by name (case-insensitive)")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of results to display")
    parser.add_argument("--host", type=str, default="localhost", help="openLCA IPC Server host")
    parser.add_argument("--port", type=int, default=8080, help="openLCA IPC Server port")
