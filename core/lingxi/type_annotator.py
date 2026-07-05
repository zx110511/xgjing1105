"""
灵犀·类型注解器

功能:
  1. 扫描缺类型注解的函数参数和返回值
  2. 从函数体推断类型(静态分析启发式)
  3. 从调用点推断类型(跨函数)
  4. 生成类型注解并插入源文件
  5. 验证插入后语法正确
"""

from __future__ import annotations

import ast
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class MissingAnnotation:
    """缺失类型注解的条目"""
    func_name: str
    line: int
    untyped_params: List[str] = field(default_factory=list)  # 无类型参数名
    missing_return: bool = False
    inferred_params: Dict[str, str] = field(default_factory=dict)  # 推断的参数类型
    inferred_return: Optional[str] = None  # 推断的返回类型
    is_method: bool = False
    is_async: bool = False


@dataclass
class AnnotationReport:
    """注解生成报告"""
    total_scanned: int = 0
    missing_count: int = 0
    generated_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    details: List[Dict] = field(default_factory=list)


# 类型推断启发式规则
_TYPE_HINTS: Dict[str, str] = {
    # 常见赋值模式
    '""': "str",
    "''": "str",
    "[]": "list",
    "{}": "dict",
    "()": "tuple",
    "set()": "set",
    "0": "int",
    "1": "int",
    "True": "bool",
    "False": "bool",
    "None": "None",
    "0.0": "float",
    "0.0f": "float",
}


def scan_missing_annotations(file_path: str | Path) -> List[MissingAnnotation]:
    """扫描文件中缺失类型注解的函数。

    Args:
        file_path: Python文件路径

    Returns:
        缺失注解条目列表
    """
    file_path = Path(file_path)
    try:
        source = file_path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    results: List[MissingAnnotation] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        untyped_params = []
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            if arg.arg in ("self", "cls"):
                continue
            if arg.annotation is None:
                untyped_params.append(arg.arg)

        missing_return = node.returns is None

        if not untyped_params and not missing_return:
            continue

        is_method = _check_is_method(node, tree)

        results.append(MissingAnnotation(
            func_name=node.name,
            line=node.lineno,
            untyped_params=untyped_params,
            missing_return=missing_return,
            is_method=is_method,
            is_async=isinstance(node, ast.AsyncFunctionDef),
        ))

    return results


def _check_is_method(node: ast.FunctionDef | ast.AsyncFunctionDef, tree: ast.AST) -> bool:
    """判断函数是否是类方法。"""
    for parent in ast.walk(tree):
        if isinstance(parent, ast.ClassDef):
            for child in parent.body:
                if child is node:
                    return True
    return False


def infer_param_type(func_node: ast.FunctionDef | ast.AsyncFunctionDef, param_name: str) -> Optional[str]:
    """从函数体推断参数类型。

    使用启发式规则:
    1. 参数参与算术运算 → int/float
    2. 参数调用字符串方法 → str
    3. 参数用于len() → 集合类型
    4. 参数参与比较运算 → 根据比较值推断
    5. 参数作为dict key → str

    Args:
        func_node: AST函数节点
        param_name: 参数名

    Returns:
        推断的类型字符串，无法推断返回None
    """
    for node in ast.walk(func_node):
        # x + 数字 → int/float
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            left_uses = _name_in_node(node.left, param_name)
            right_uses = _name_in_node(node.right, param_name)
            if left_uses or right_uses:
                # 检查另一侧是否为数字
                other = node.right if left_uses else node.left
                if isinstance(other, ast.Constant):
                    if isinstance(other.value, bool):
                        pass  # bool是int子类，跳过
                    elif isinstance(other.value, int):
                        return "int"
                    elif isinstance(other.value, float):
                        return "float"
                return "int"

        # x.startswith / x.endswith / x.split / x.strip → str
        if isinstance(node, ast.Attribute) and _uses_name(node.value, param_name):
            str_methods = {"startswith", "endswith", "split", "strip", "lower", "upper",
                          "replace", "join", "find", "rfind", "lstrip", "rstrip", "capitalize"}
            if node.attr in str_methods:
                return "str"

        # len(x) → 集合类型
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "len" and len(node.args) > 0:
                if _uses_name(node.args[0], param_name):
                    return "list"

        # x.append / x.extend → list
        if isinstance(node, ast.Attribute) and _uses_name(node.value, param_name):
            list_methods = {"append", "extend", "insert", "pop", "remove", "sort", "reverse"}
            if node.attr in list_methods:
                return "list"

        # x.get / x.keys / x.values / x.items → dict
        if isinstance(node, ast.Attribute) and _uses_name(node.value, param_name):
            dict_methods = {"get", "keys", "values", "items", "update", "pop", "setdefault"}
            if node.attr in dict_methods:
                return "dict"

        # x.write / x.read → IO
        if isinstance(node, ast.Attribute) and _uses_name(node.value, param_name):
            io_methods = {"write", "read", "readline", "readlines", "writelines"}
            if node.attr in io_methods:
                return "IO"

        # f-string中使用 → str
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.FormattedValue) and _uses_name(value.value, param_name):
                    return "str"

        # 比较运算
        if isinstance(node, ast.Compare) and _uses_name(node.left, param_name):
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant):
                    if isinstance(comparator.value, int):
                        return "int"
                    if isinstance(comparator.value, str):
                        return "str"
                    if isinstance(comparator.value, float):
                        return "float"

    return None


def infer_return_type(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[str]:
    """推断函数返回类型。

    规则:
    1. 无return → None
    2. return常量 → 对应类型
    3. return变量 → 从赋值推断
    4. return函数调用 → 从函数名推断
    5. 有多个return → Union

    Args:
        func_node: AST函数节点

    Returns:
        推断的返回类型字符串
    """
    return_types: Set[str] = set()

    for node in ast.walk(func_node):
        if isinstance(node, ast.Return) and node.value is not None:
            rt = _infer_expr_type(node.value)
            if rt:
                return_types.add(rt)

    if not return_types:
        # 无return语句 → None
        has_return = any(
            isinstance(n, ast.Return) for n in ast.walk(func_node)
        )
        if not has_return or all(
            isinstance(n, ast.Return) and n.value is None
            for n in ast.walk(func_node) if isinstance(n, ast.Return)
        ):
            return "None"

    if len(return_types) == 1:
        return return_types.pop()

    if len(return_types) > 1:
        return f"Union[{', '.join(sorted(return_types))}]"

    return None


def _infer_expr_type(node: ast.expr) -> Optional[str]:
    """推断表达式的类型。"""
    if isinstance(node, ast.Constant):
        type_map = {int: "int", str: "str", float: "float", bool: "bool", type(None): "None"}
        return type_map.get(type(node.value))

    if isinstance(node, ast.Name):
        name_type_map = {"True": "bool", "False": "bool", "None": "None"}
        return name_type_map.get(node.id)

    if isinstance(node, ast.List):
        return "list"
    if isinstance(node, ast.Dict):
        return "dict"
    if isinstance(node, ast.Tuple):
        return "tuple"
    if isinstance(node, ast.Set):
        return "set"

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            constructor_map = {
                "str": "str", "int": "int", "float": "float", "bool": "bool",
                "list": "list", "dict": "dict", "tuple": "tuple", "set": "set",
                "frozenset": "frozenset", "bytes": "bytes", "bytearray": "bytearray",
            }
            return constructor_map.get(node.func.id)
        if isinstance(node.func, ast.Attribute):
            # method call → infer from method
            if node.func.attr in ("keys", "values", "items"):
                return "list"
            if node.func.attr == "get":
                return "Any"

    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            left_type = _infer_expr_type(node.left)
            right_type = _infer_expr_type(node.right)
            if left_type == "str" or right_type == "str":
                return "str"
            if left_type == "float" or right_type == "float":
                return "float"
            return "int"

    if isinstance(node, ast.IfExp):
        return _infer_expr_type(node.body)

    return None


def _uses_name(node: ast.AST, name: str) -> bool:
    """检查AST节点是否使用了指定名称。"""
    if isinstance(node, ast.Name):
        return node.id == name
    return False


def _name_in_node(node: ast.AST, name: str) -> bool:
    """检查AST节点或其子节点中是否使用了指定名称。"""
    if isinstance(node, ast.Name):
        return node.id == name
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == name:
            return True
    return False


def insert_annotation(
    file_path: str | Path,
    func_name: str,
    param_types: Dict[str, str],
    return_type: Optional[str] = None,
    line_number: int = 0,
) -> bool:
    """将类型注解插入到源文件中。

    Args:
        file_path: 文件路径
        func_name: 函数名
        param_types: 参数名→类型映射
        return_type: 返回类型
        line_number: 函数定义行号

    Returns:
        是否成功插入
    """
    file_path = Path(file_path)
    try:
        source = file_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return False

    # 使用正则替换方式插入注解
    lines = source.splitlines(keepends=True)

    # 找到目标函数行
    target_line = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("async def "):
            # 提取函数名
            match = re.match(r'(?:async\s+)?def\s+(\w+)', stripped)
            if match and match.group(1) == func_name:
                target_line = i
                break

    if target_line is None:
        return False

    # 解析并重建def行
    def_line = lines[target_line]
    # 提取缩进
    indent = ""
    for ch in def_line:
        if ch in (" ", "\t"):
            indent += ch
        else:
            break

    # 解析参数列表
    new_line = _rebuild_def_line(def_line, indent, func_name, param_types, return_type)
    if new_line is None:
        return False

    lines[target_line] = new_line

    try:
        file_path.write_text("".join(lines), encoding="utf-8-sig")
        return True
    except OSError:
        return False


def _rebuild_def_line(
    def_line: str,
    indent: str,
    func_name: str,
    param_types: Dict[str, str],
    return_type: Optional[str],
) -> Optional[str]:
    """重建def行，添加类型注解。"""
    # 提取参数部分
    match = re.match(r'((?:async\s+)?def\s+\w+\s*\()(.*)', def_line.strip())
    if not match:
        return None

    params_str = _extract_params_str(def_line)

    # 解析参数
    params = _split_params(params_str)
    new_params = []
    for param in params:
        param = param.strip()
        if not param:
            continue
        # 检查是否已有类型注解
        if ":" in param and "=" not in param.split(":")[0]:
            new_params.append(param)
            continue
        # 提取参数名
        param_name = param.split("=")[0].split(":")[0].strip()
        if param_name in ("self", "cls"):
            new_params.append(param_name)
            continue
        if param_name in param_types:
            type_str = param_types[param_name]
            if "=" in param:
                # 有默认值
                parts = param.split("=", 1)
                new_params.append(f"{param_name}: {type_str} = {parts[1].strip()}")
            else:
                new_params.append(f"{param_name}: {type_str}")
        else:
            new_params.append(param)

    # 构建新def行
    prefix = "async " if def_line.strip().startswith("async") else ""
    ret_annotation = f" -> {return_type}" if return_type else ""
    new_line = f"{indent}{prefix}def {func_name}({', '.join(new_params)}){ret_annotation}:\n"

    return new_line


def _extract_params_str(def_line: str) -> str:
    """从def行提取参数字符串。"""
    # 找到第一个(和最后一个)
    start = def_line.index("(") + 1
    depth = 1
    end = start
    for i in range(start, len(def_line)):
        if def_line[i] == "(":
            depth += 1
        elif def_line[i] == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    return def_line[start:end]


def _split_params(params_str: str) -> List[str]:
    """分割参数字符串，考虑嵌套括号。"""
    params = []
    current = ""
    depth = 0
    for ch in params_str:
        if ch in ("(", "[", "{"):
            depth += 1
            current += ch
        elif ch in (")", "]", "}"):
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            params.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        params.append(current)
    return params


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
    """处理单个文件，补全缺失类型注解。

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

    try:
        source = file_path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, OSError) as e:
        result["errors"].append(f"解析失败: {e}")
        return result

    missing_list = scan_missing_annotations(file_path)
    result["missing"] = [
        {"name": m.func_name, "line": m.line, "untyped": m.untyped_params, "missing_return": m.missing_return}
        for m in missing_list
    ]

    if dry_run or not missing_list:
        return result

    # 备份
    backup_dir = file_path.parent / ".annotation_backup"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f"{file_path.name}.bak"
    try:
        shutil.copy2(file_path, backup_path)
    except OSError as e:
        result["errors"].append(f"备份失败: {e}")
        return result

    # 推断类型并插入
    for m in missing_list:
        # 找到对应的AST节点
        func_node = _find_func_node(tree, m.func_name, m.line)
        if func_node is None:
            continue

        # 推断参数类型
        param_types: Dict[str, str] = {}
        for param in m.untyped_params:
            inferred = infer_param_type(func_node, param)
            if inferred:
                param_types[param] = inferred

        # 推断返回类型
        ret_type = None
        if m.missing_return:
            ret_type = infer_return_type(func_node)

        if param_types or ret_type:
            success = insert_annotation(file_path, m.func_name, param_types, ret_type, m.line)
            if success:
                result["generated"].append({
                    "name": m.func_name,
                    "param_types": param_types,
                    "return_type": ret_type,
                })
            else:
                result["errors"].append(f"插入失败: {m.func_name}")

    # 验证语法
    if not verify_syntax(file_path):
        result["errors"].append("语法验证失败，恢复备份")
        shutil.copy2(backup_path, file_path)
        result["generated"] = []

    return result


def _find_func_node(tree: ast.AST, name: str, line: int) -> Optional[ast.FunctionDef | ast.AsyncFunctionDef]:
    """在AST中查找指定函数节点。"""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name and node.lineno == line:
                return node
    return None


def process_directory(directory: str | Path, dry_run: bool = True) -> AnnotationReport:
    """处理整个目录，补全缺失类型注解。

    Args:
        directory: 目录路径
        dry_run: 是否仅预览不修改

    Returns:
        完整报告
    """
    directory = Path(directory)
    report = AnnotationReport()

    for py_file in sorted(directory.rglob("*.py")):
        if ".annotation_backup" in str(py_file) or py_file.name.startswith("_"):
            continue

        missing = scan_missing_annotations(py_file)
        report.total_scanned += 1
        report.missing_count += len(missing)

        if not missing:
            continue

        if dry_run:
            report.skipped_count += len(missing)
            report.details.append({
                "file": str(py_file.relative_to(directory)),
                "missing": [
                    {"name": m.func_name, "untyped": m.untyped_params, "missing_return": m.missing_return}
                    for m in missing
                ],
            })
        else:
            file_result = process_file(py_file, dry_run=False)
            report.generated_count += len(file_result.get("generated", []))
            report.error_count += len(file_result.get("errors", []))
            report.details.append(file_result)

    return report
