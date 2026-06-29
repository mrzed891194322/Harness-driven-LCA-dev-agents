import re
from pathlib import Path

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

def load_user_values(filepath: Path) -> list[str]:
    """
    从目标 plan.md 文件中提取出用户已填写的 12 个区域内容。
    """
    if not filepath.exists():
        return []
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return []
        
    # 正则匹配 \s*---\s*\*\*\*✍️ 用户填写内容区\*\*\* ... \s*---
    regex = re.compile(r'(?s)\s*---\s*\*\*\*✍️ 用户填写内容区\*\*\*.*?\s*---')
    val_regex = re.compile(r'\*\*\*✍️ 用户填写内容区\*\*\*\s*(.*?)\s*---', re.DOTALL)
    
    values = []
    matches = list(regex.finditer(content))
    for match in matches:
        block_text = match.group(0)
        val_match = val_regex.search(block_text)
        if val_match:
            values.append(val_match.group(1).strip())
        else:
            values.append("")
    return values

def save_user_values(template_path: Path, target_path: Path, values: list[str]) -> bool:
    """
    把用户填写的文本框内容整合进 clean 的 plan.md 模板中，并保存到目标位置。
    """
    if not template_path.exists():
        return False
    try:
        content = template_path.read_text(encoding="utf-8")
        regex = re.compile(r'(?s)(\s*)---\s*\*\*\*✍️ 用户填写内容区\*\*\*.*?\s*---')
        
        matches = list(regex.finditer(content))
        new_content = ""
        last_idx = 0
        
        for i, match in enumerate(matches):
            val = values[i] if i < len(values) else ""
            
            # 添加前置 markdown 文本
            new_content += content[last_idx:match.start()]
            
            # 获取当前区块的前导缩进（即 match.group(1) 或者是匹配到的空白）
            indent = match.group(1) or ""
            # 去除缩进里的换行符，只保留空格/制表符
            indent = indent.replace("\n", "").replace("\r", "")
            
            # 拼接填写好的区块内容
            new_block = f"\n{indent}---\n{indent}***✍️ 用户填写内容区***\n\n{indent}{val}\n\n{indent}---"
            new_content += new_block
            last_idx = match.end()
            
        new_content += content[last_idx:]
        
        # 确保目标文件夹存在并写入文件
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(new_content, encoding="utf-8")
        return True
    except Exception:
        return False

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
