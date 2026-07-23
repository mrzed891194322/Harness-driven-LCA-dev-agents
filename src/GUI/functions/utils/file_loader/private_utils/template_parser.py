import re
from pathlib import Path
from functions.utils.file_loader.private_utils.template_metadata import split_front_matter

def parse_plan_template(filepath: Path) -> list[dict]:
    """
    解析 plan.md 模板文件，将其拆分为静态 markdown 块和用户可填写的文本框块。
    并在每个 ## 或 ### 标题前插入锚点。
    """
    if not filepath.exists():
        return [{"type": "markdown", "content": f"⚠️ **模板文件不存在**: `{filepath.as_posix()}`"}]
        
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        return [{"type": "markdown", "content": f"⚠️ **读取模板文件出错**: {str(e)}"}]

    _, content = split_front_matter(content)

    # 正则匹配 \s*---\s*\*\*\*✍️ 用户填写内容区\*\*\* ... \s*---，允许有缩进空格
    regex = re.compile(r'(?s)\s*---\s*\*\*\*✍️ 用户填写内容区\*\*\*.*?\s*---')
    
    parts = []
    last_idx = 0
    
    header_counter = [0]
    def add_anchors(match):
        header_counter[0] += 1
        level = match.group(1)
        title = match.group(2)
        anchor_id = f"plan-header-{header_counter[0]}"
        return f'<div id="{anchor_id}"></div>\n\n{level} {title}'
    
    matches = list(regex.finditer(content))
    for i, match in enumerate(matches):
        # 1. 提取前置的 Markdown 内容，并清理尾部的换行与空白
        md_text = content[last_idx:match.start()].rstrip()
        if md_text:
            # 在 Markdown 内容块中为 ## 和 ### 标题动态添加锚点 ID
            md_text_with_anchors = re.sub(r'^(#{2,3})\s+(.*)$', add_anchors, md_text, flags=re.MULTILINE)
            parts.append({"type": "markdown", "content": md_text_with_anchors})
            
        # 2. 从前置 Markdown 中提取最后一个粗体文字作为文本框的 Label
        label = f"输入区域 {i+1}"
        label_matches = re.findall(r'\*\*([^*:\n]+)\*\*', md_text)
        if label_matches:
            label = label_matches[-1].strip()
            
        parts.append({
            "type": "textbox",
            "label": label,
            "placeholder": f"请输入 {label}..."
        })
        
        last_idx = match.end()
        
    # 3. 提取尾部的 Markdown 内容
    md_text = content[last_idx:].strip()
    if md_text:
        md_text_with_anchors = re.sub(r'^(#{2,3})\s+(.*)$', add_anchors, md_text, flags=re.MULTILINE)
        parts.append({"type": "markdown", "content": md_text_with_anchors})
        
    return parts
