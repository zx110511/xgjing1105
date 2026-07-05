"""
灵犀·自愈之手 — Docstring生成器

功能:
  1. 扫描指定模块，识别缺docstring的函数/类
  2. 解析函数签名(参数+返回值+类型注解)
  3. 基于签名规则生成模板docstring
  4. 自动插入到源文件正确位置
  5. 验证插入后文件语法正确
  6. 生成变更报告
"""

from __future__ import annotations

import ast
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class MissingDoc:
    """缺失docstring的条目"""
    name: str
    kind: str  # "function" / "async_function" / "class"
    line: int
    end_line: int
    args: List[str] = field(default_factory=list)
    returns: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    is_method: bool = False


@dataclass
class FuncSignature:
    """函数签名信息"""
    name: str
    params: List[Tuple[str, Optional[str], Optional[str]]] = field(default_factory=list)  # (name, type, default)
    return_type: Optional[str] = None
    is_async: bool = False
    is_method: bool = False


@dataclass
class DocstringReport:
    """docstring生成报告"""
    total_scanned: int = 0
    missing_count: int = 0
    generated_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    details: List[Dict] = field(default_factory=list)


def scan_missing_docstrings(file_path: str | Path) -> List[MissingDoc]:
    """扫描文件中缺失docstring的函数和类。

    Args:
        file_path: Python文件路径

    Returns:
        缺失docstring条目列表
    """
    file_path = Path(file_path)
    try:
        source = file_path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    missing: List[MissingDoc] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            docstring = ast.get_docstring(node)
            if docstring is None:
                args = _extract_args(node)
                returns = _extract_return_type(node)
                decorators = _extract_decorators(node)
                is_method = _is_method(node, tree)

                missing.append(MissingDoc(
                    name=node.name,
                    kind="async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    args=args,
                    returns=returns,
                    decorators=decorators,
                    is_method=is_method,
                ))

        elif isinstance(node, ast.ClassDef):
            docstring = ast.get_docstring(node)
            if docstring is None:
                missing.append(MissingDoc(
                    name=node.name,
                    kind="class",
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                ))

    return missing


def _extract_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
    """提取函数参数名列表。"""
    args = []
    for arg in node.args.args:
        if arg.arg == "self" or arg.arg == "cls":
            continue
        args.append(arg.arg)
    for arg in node.args.posonlyargs:
        if arg.arg not in ("self", "cls"):
            args.append(arg.arg)
    for arg in node.args.kwonlyargs:
        args.append(arg.arg)
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    return args


def _extract_return_type(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[str]:
    """提取返回类型注解。"""
    if node.returns is None:
        return None
    return _annotation_to_str(node.returns)


def _annotation_to_str(annotation: ast.expr) -> str:
    """将AST注解节点转为字符串。"""
    if isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Constant):
        return str(annotation.value)
    elif isinstance(annotation, ast.Attribute):
        return f"{_annotation_to_str(annotation.value)}.{annotation.attr}"
    elif isinstance(annotation, ast.Subscript):
        return f"{_annotation_to_str(annotation.value)}[{_annotation_to_str(annotation.slice)}]"
    elif isinstance(annotation, ast.Tuple):
        return ", ".join(_annotation_to_str(elt) for elt in annotation.elts)
    elif isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return f"{_annotation_to_str(annotation.left)} | {_annotation_to_str(annotation.right)}"
    return "Any"


def _extract_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
    """提取装饰器名称。"""
    decorators = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            decorators.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            decorators.append(dec.attr)
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                decorators.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                decorators.append(dec.func.attr)
    return decorators


def _is_method(node: ast.FunctionDef | ast.AsyncFunctionDef, tree: ast.AST) -> bool:
    """判断函数是否是类方法。"""
    for parent in ast.walk(tree):
        if isinstance(parent, ast.ClassDef):
            for child in parent.body:
                if child is node:
                    return True
    return False


def parse_function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> FuncSignature:
    """解析函数签名。

    Args:
        node: AST函数定义节点

    Returns:
        函数签名信息
    """
    params = []
    for arg in node.args.args:
        type_str = _annotation_to_str(arg.annotation) if arg.annotation else None
        params.append((arg.arg, type_str, None))

    for arg in node.args.posonlyargs:
        type_str = _annotation_to_str(arg.annotation) if arg.annotation else None
        params.append((arg.arg, type_str, None))

    # 关键字参数
    for arg in node.args.kwonlyargs:
        type_str = _annotation_to_str(arg.annotation) if arg.annotation else None
        # 查找默认值
        default_val = None
        kw_defaults_start = len(node.args.kwonlyargs) - len(node.args.kw_defaults)
        idx = node.args.kwonlyargs.index(arg)
        if idx < len(node.args.kw_defaults) and node.args.kw_defaults[idx] is not None:
            default_val = _annotation_to_str(node.args.kw_defaults[idx]) if isinstance(node.args.kw_defaults[idx], ast.expr) else None
        params.append((arg.arg, type_str, default_val))

    return_type = _extract_return_type(node)

    return FuncSignature(
        name=node.name,
        params=params,
        return_type=return_type,
        is_async=isinstance(node, ast.AsyncFunctionDef),
        is_method=any(p[0] in ("self", "cls") for p in params) or (len(params) > 0 and params[0][0] in ("self", "cls")),
    )


def generate_docstring(missing: MissingDoc, sig: Optional[FuncSignature] = None) -> str:
    """基于签名规则生成模板docstring。

    Args:
        missing: 缺失docstring条目
        sig: 可选的函数签名信息

    Returns:
        生成的docstring文本
    """
    if missing.kind == "class":
        return f'{missing.name}类。'

    # 函数/方法
    lines = []

    # 描述行
    if missing.kind == "async_function":
        lines.append(f"异步执行{missing.name}。")
    else:
        lines.append(f"执行{missing.name}。")

    # 参数文档
    if missing.args:
        lines.append("")
        lines.append("Args:")
        for arg in missing.args:
            if arg.startswith("*") or arg.startswith("**"):
                lines.append(f"    {arg}: 可变参数")
            else:
                lines.append(f"    {arg}: 参数说明")

    # 返回值文档
    if missing.returns:
        lines.append("")
        lines.append(f"Returns:")
        lines.append(f"    {missing.returns}: 返回值说明")

    return "\n".join(lines)


def insert_docstring(
    file_path: str | Path,
    func_name: str,
    docstring: str,
    line_number: int,
) -> bool:
    """将docstring插入到源文件中。

    Args:
        file_path: 文件路径
        func_name: 函数名
        docstring: docstring内容
        line_number: 函数定义行号

    Returns:
        是否成功插入
    """
    file_path = Path(file_path)
    try:
        lines = file_path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    except (OSError, UnicodeDecodeError):
        return False

    if line_number < 1 or line_number > len(lines):
        return False

    # 找到函数体第一行(def行的下一行)
    insert_idx = line_number  # 0-based index = line_number - 1

    # 检查下一行是否已有docstring
    if insert_idx < len(lines):
        next_line = lines[insert_idx].strip()
        if next_line.startswith('"""') or next_line.startswith("'''"):
            return False  # 已有docstring

    # 获取缩进
    def_line = lines[insert_idx - 1]
    indent = ""
    for ch in def_line:
        if ch in (" ", "\t"):
            indent += ch
        else:
            break
    body_indent = indent + "    "

    # 构建docstring行
    doc_lines = [f'{body_indent}"""\n']
    for dl in docstring.split("\n"):
        doc_lines.append(f"{body_indent}{dl}\n")
    doc_lines.append(f'{body_indent}"""\n')

    # 插入
    for i, doc_line in enumerate(doc_lines):
        lines.insert(insert_idx + i, doc_line)

    # 写回
    try:
        file_path.write_text("".join(lines), encoding="utf-8-sig")
        return True
    except OSError:
        return False


def verify_syntax(file_path: str | Path) -> bool:
    """验证文件Python语法正确。

    Args:
        file_path: 文件路径

    Returns:
        语法是否正确
    """
    file_path = Path(file_path)
    try:
        source = file_path.read_text(encoding="utf-8-sig")
        ast.parse(source)
        return True
    except (SyntaxError, UnicodeDecodeError, OSError):
        return False


def process_file(file_path: str | Path, dry_run: bool = True) -> Dict:
    """处理单个文件，补全缺失docstring。

    Args:
        file_path: 文件路径
        dry_run: 是否仅预览不修改

    Returns:
        处理结果字典
    """
    file_path = Path(file_path)
    result = {
        "file": str(file_path),
        "missing": [],
        "generated": [],
        "errors": [],
        "dry_run": dry_run,
    }

    missing_list = scan_missing_docstrings(file_path)
    result["missing"] = [
        {"name": m.name, "kind": m.kind, "line": m.line}
        for m in missing_list
    ]

    if dry_run or not missing_list:
        return result

    # 备份
    backup_dir = file_path.parent / ".docstring_backup"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f"{file_path.name}.bak"
    try:
        shutil.copy2(file_path, backup_path)
    except OSError as e:
        result["errors"].append(f"备份失败: {e}")
        return result

    # 从后往前插入(避免行号偏移)
    for m in reversed(missing_list):
        docstring = generate_docstring(m)
        success = insert_docstring(file_path, m.name, docstring, m.line)
        if success:
            result["generated"].append({"name": m.name, "line": m.line})
        else:
            result["errors"].append(f"插入失败: {m.name} (line {m.line})")

    # 验证语法
    if not verify_syntax(file_path):
        result["errors"].append("语法验证失败，恢复备份")
        shutil.copy2(backup_path, file_path)
        result["generated"] = []

    return result


def process_directory(directory: str | Path, dry_run: bool = True) -> DocstringReport:
    """处理整个目录，补全缺失docstring。

    Args:
        directory: 目录路径
        dry_run: 是否仅预览不修改

    Returns:
        完整报告
    """
    directory = Path(directory)
    report = DocstringReport()

    for py_file in sorted(directory.rglob("*.py")):
        # 跳过备份和临时文件
        if ".docstring_backup" in str(py_file) or py_file.name.startswith("_"):
            continue

        missing = scan_missing_docstrings(py_file)
        report.total_scanned += 1
        report.missing_count += len(missing)

        if not missing:
            continue

        if dry_run:
            report.skipped_count += len(missing)
            report.details.append({
                "file": str(py_file.relative_to(directory)),
                "missing": [{"name": m.name, "kind": m.kind, "line": m.line} for m in missing],
            })
        else:
            file_result = process_file(py_file, dry_run=False)
            report.generated_count += len(file_result.get("generated", []))
            report.error_count += len(file_result.get("errors", []))
            report.details.append(file_result)

    return report
