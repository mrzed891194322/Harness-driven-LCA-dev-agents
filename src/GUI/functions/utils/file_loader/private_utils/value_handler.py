import re
from pathlib import Path

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
