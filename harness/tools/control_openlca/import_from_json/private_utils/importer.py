import sys
from pathlib import Path

from utils.workflow import legacy_clear_category, legacy_import_lci

def clear_category(client, project_name: str):
    if not project_name:
        return
        
    print(f"检查 openLCA 中是否存在同名分类/目录: '{project_name}'...")
    result = legacy_clear_category(client, project_name, emit=print)
    if result["deleted_count"] == 0 and result["failed_count"] == 0:
        print(f"未在 openLCA 中找到分类 '{project_name}' 下的现有内容。无需清空。")
    else:
        print(
            f"分类 '{project_name}' 的清空操作已完成："
            f"删除 {result['deleted_count']}，失败 {result['failed_count']}。"
        )

def import_json_files(client, json_dir: Path):
    try:
        # 直接读取工作目录的名称
        project_name = Path.cwd().name
        if not project_name:
            project_name = 'auto_LCA_project'
    except Exception as e:
        print(f"[警告] 读取工作目录名称失败: {e}")
        project_name = 'auto_LCA_project'
    print(f"已自动解析分类/项目名称为: '{project_name}'")

    if not json_dir.exists():
        print(f"[错误] 指定的目录不存在: {json_dir}")
        sys.exit(1)
    result = legacy_import_lci(client, json_dir, project_name, emit=print)
    if result["failed_count"]:
        print(
            f"[警告] 导入完成但存在 {result['failed_count']} 个失败；"
            f"成功 {result['success_count']} 个。"
        )
