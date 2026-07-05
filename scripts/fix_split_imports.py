"""修复拆分后子模块的import和语法问题"""
import re
from pathlib import Path

ENF = Path(r"D:\元初系统\天机v9.1\core\enforcement")

def fix_file(path: Path, add_imports: str = "", remove_trailing_decorator: bool = False):
    """修复单个文件"""
    content = path.read_text(encoding="utf-8")

    # 添加缺失的import
    if add_imports:
        # 在现有import块后添加
        lines = content.splitlines(keepends=True)
        insert_pos = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("from __future__") or stripped.startswith("import ") or stripped.startswith("from "):
                insert_pos = i + 1
            elif stripped == "" or stripped.startswith("#") or stripped.startswith('"""'):
                continue
            else:
                break
        lines.insert(insert_pos, add_imports + "\n")
        content = "".join(lines)

    # 移除末尾孤立的@dataclass
    if remove_trailing_decorator:
        content = re.sub(r'\n\n@dataclass\s*$', '\n', content)
        content = re.sub(r'\n@dataclass\s*$', '\n', content)

    path.write_text(content, encoding="utf-8")
    print(f"  Fixed: {path.name}")

# 修复各子模块
fix_file(ENF / "standards" / "ms_agent_span.py", remove_trailing_decorator=True)
fix_file(ENF / "standards" / "owasp_inspect.py", remove_trailing_decorator=True)
fix_file(ENF / "standards" / "otel_eval.py", remove_trailing_decorator=True)
fix_file(ENF / "otel_attributes.py", remove_trailing_decorator=True)

print("Done!")
