import re
from pathlib import Path

def extract_plan_toc(filepath: Path) -> str:
    """
    扫描 plan.md，提取二级和三级标题，并生成带有锚点的 HTML 目录导航。
    """
    if not filepath.exists():
        return ""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return ""
        
    toc_lines = ["<div class='toc-wrapper'>", "<h4>📋 计划目录导航</h4>"]
    header_count = 0
    for line in content.splitlines():
        match = re.match(r'^(#{2,3})\s+(.*)$', line)
        if match:
            level_hashes = match.group(1)
            title = match.group(2).strip()
            level = len(level_hashes)
            
            header_count += 1
            anchor_id = f"plan-header-{header_count}"
            indent_class = f"toc-level-{level}"
            toc_lines.append(f"<a href='#{anchor_id}' class='toc-link {indent_class}'>{title}</a>")
            
    toc_lines.append("</div>")
    return "\n".join(toc_lines)
