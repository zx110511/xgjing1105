"""
灵犀·架构之眼 — 依赖扫描器

功能:
  1. 扫描目录所有 .py 文件的 import 关系
  2. 构建有向依赖图
  3. 检测循环依赖
  4. 标记死代码(未被引用的函数/类)
  5. 计算模块耦合度
  6. 输出 DOT 格式可视化
"""

from __future__ import annotations

import ast
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class ImportInfo:
    """单条import信息"""
    source_file: str
    module_name: str
    imported_names: List[str] = field(default_factory=list)
    is_relative: bool = False
    level: int = 0
    line_number: int = 0
    is_conditional: bool = False  # try/except ImportError 内


@dataclass
class DeadCodeItem:
    """死代码条目"""
    name: str
    kind: str  # "function" / "class" / "variable"
    file: str
    line: int
    references: int = 0


@dataclass
class ScanReport:
    """扫描报告"""
    total_files: int = 0
    total_imports: int = 0
    total_functions: int = 0
    total_classes: int = 0
    cycles: List[List[str]] = field(default_factory=list)
    dead_code: List[DeadCodeItem] = field(default_factory=list)
    coupling: Dict[str, float] = field(default_factory=dict)
    imports: Dict[str, Set[str]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


def scan_imports(directory: str | Path) -> Dict[str, List[ImportInfo]]:
    """扫描目录下所有Python文件的import关系。

    Args:
        directory: 要扫描的目录路径

    Returns:
        文件路径 -> ImportInfo列表的映射
    """
    directory = Path(directory)
    result: Dict[str, List[ImportInfo]] = {}

    for py_file in sorted(directory.rglob("*.py")):
        rel_path = str(py_file.relative_to(directory))
        try:
            imports = _parse_file_imports(py_file)
            result[rel_path] = imports
        except Exception as e:
            result[rel_path] = []
            # 记录错误但不中断扫描

    return result


def _parse_file_imports(file_path: Path) -> List[ImportInfo]:
    """解析单个文件的import语句。"""
    try:
        source = file_path.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError):
        return []

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    imports: List[ImportInfo] = []
    rel_path = str(file_path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ImportInfo(
                    source_file=rel_path,
                    module_name=alias.name,
                    imported_names=[alias.asname or alias.name],
                    line_number=node.lineno,
                    is_conditional=_is_inside_try_import(node, tree),
                ))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            is_relative = node.level > 0
            imports.append(ImportInfo(
                source_file=rel_path,
                module_name=module,
                imported_names=names,
                is_relative=is_relative,
                level=node.level,
                line_number=node.lineno,
                is_conditional=_is_inside_try_import(node, tree),
            ))

    return imports


def _is_inside_try_import(node: ast.AST, tree: ast.AST) -> bool:
    """检查节点是否在 try/except ImportError 块内。

    import在try body中，且except捕获ImportError，则视为条件import。
    """
    # 构建父节点映射
    parent_map: Dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[id(child)] = parent

    # 向上遍历父链，查找try/except ImportError
    current = parent_map.get(id(node))
    while current is not None:
        if isinstance(current, ast.Try):
            # 检查该try是否有ImportError handler
            has_import_error_handler = False
            for handler in current.handlers:
                if handler.type is not None:
                    exc_names = []
                    if isinstance(handler.type, ast.Name):
                        exc_names.append(handler.type.id)
                    elif isinstance(handler.type, ast.Tuple):
                        exc_names.extend(
                            elt.id for elt in handler.type.elts
                            if isinstance(elt, ast.Name)
                        )
                    if "ImportError" in exc_names:
                        has_import_error_handler = True
                        break

            if has_import_error_handler:
                # 检查node是否在该try的body内（不是handler/orelse/finally内）
                for body_node in current.body:
                    for descendant in ast.walk(body_node):
                        if descendant is node:
                            return True
        current = parent_map.get(id(current))

    return False


def build_dependency_graph(
    imports: Dict[str, List[ImportInfo]],
    base_package: str = "",
) -> Dict[str, Set[str]]:
    """从import信息构建模块依赖图。

    Args:
        imports: scan_imports的输出
        base_package: 基础包名，用于过滤外部依赖

    Returns:
        模块名 -> 依赖模块名集合的映射
    """
    graph: Dict[str, Set[str]] = defaultdict(set)

    for source_file, import_list in imports.items():
        module_name = source_file.replace(os.sep, ".").replace("/", ".").removesuffix(".py")
        if module_name.endswith(".__init__"):
            module_name = module_name[:-9]

        for imp in import_list:
            target = imp.module_name
            if imp.is_relative and base_package:
                # 解析相对import
                parts = module_name.split(".")
                if imp.level > 0 and len(parts) >= imp.level:
                    base_parts = parts[:-imp.level]
                    if target:
                        target = ".".join(base_parts + [target])
                    else:
                        target = ".".join(base_parts)

            # 过滤: 只保留项目内依赖
            if base_package and not target.startswith(base_package):
                # 检查是否是同目录下的相对import
                if not imp.is_relative:
                    continue

            graph[module_name].add(target)

    return dict(graph)


def detect_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """检测依赖图中的循环依赖。

    使用DFS着色算法，时间复杂度O(V+E)。

    Args:
        graph: 依赖图

    Returns:
        循环路径列表
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = defaultdict(int)
    cycles: List[List[str]] = []
    path: List[str] = []

    def dfs(node: str) -> None:
        color[node] = GRAY
        path.append(node)

        for neighbor in graph.get(node, set()):
            if color[neighbor] == GRAY:
                # 找到循环
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
            elif color[neighbor] == WHITE:
                dfs(neighbor)

        path.pop()
        color[node] = BLACK

    for node in graph:
        if color[node] == WHITE:
            dfs(node)

    return cycles


def find_dead_code(
    directory: str | Path,
    graph: Dict[str, Set[str]] | None = None,
) -> List[DeadCodeItem]:
    """扫描目录中的死代码(未被引用的函数/类)。

    Args:
        directory: 要扫描的目录
        graph: 可选的依赖图(用于跨文件引用分析)

    Returns:
        死代码条目列表
    """
    directory = Path(directory)
    definitions: Dict[str, DeadCodeItem] = {}
    references: Dict[str, int] = defaultdict(int)

    for py_file in sorted(directory.rglob("*.py")):
        rel_path = str(py_file.relative_to(directory))
        try:
            source = py_file.read_text(encoding="utf-8-sig")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        # 收集定义
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if not name.startswith("_"):  # 跳过私有方法
                    definitions[f"{rel_path}::{name}"] = DeadCodeItem(
                        name=name, kind="function", file=rel_path, line=node.lineno,
                    )
            elif isinstance(node, ast.ClassDef):
                name = node.name
                definitions[f"{rel_path}::{name}"] = DeadCodeItem(
                    name=name, kind="class", file=rel_path, line=node.lineno,
                )

        # 收集引用
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                references[node.id] += 1
            elif isinstance(node, ast.Attribute):
                references[node.attr] += 1

    # 标记死代码: 定义存在但引用为0
    dead: List[DeadCodeItem] = []
    for key, item in definitions.items():
        ref_count = references.get(item.name, 0)
        item.references = ref_count
        if ref_count == 0:
            dead.append(item)

    return dead


def calc_coupling(graph: Dict[str, Set[str]]) -> Dict[str, float]:
    """计算模块耦合度。

    耦合度 = 依赖数 / 最大可能依赖数。
    值域 [0, 1]，越高表示耦合越严重。

    Args:
        graph: 依赖图

    Returns:
        模块名 -> 耦合度映射
    """
    if not graph:
        return {}

    all_modules = set(graph.keys())
    for deps in graph.values():
        all_modules.update(deps)

    n = len(all_modules)
    max_deps = max(n - 1, 1)

    coupling: Dict[str, float] = {}
    for module, deps in graph.items():
        # 只计算项目内依赖
        internal_deps = deps & all_modules
        coupling[module] = len(internal_deps) / max_deps

    return coupling


def export_dot(graph: Dict[str, Set[str]], output_path: str | Path) -> None:
    """导出依赖图为DOT格式。

    Args:
        graph: 依赖图
        output_path: 输出文件路径
    """
    output_path = Path(output_path)
    lines = ["digraph dependencies {", '  rankdir=LR;', '  node [shape=box];']

    for module, deps in sorted(graph.items()):
        safe_name = module.replace(".", "_").replace("-", "_")
        lines.append(f'  {safe_name} [label="{module}"];')
        for dep in sorted(deps):
            safe_dep = dep.replace(".", "_").replace("-", "_")
            lines.append(f"  {safe_name} -> {safe_dep};")

    lines.append("}")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def scan_and_report(directory: str | Path, base_package: str = "") -> ScanReport:
    """一键扫描并生成完整报告。

    Args:
        directory: 要扫描的目录
        base_package: 基础包名(如"core")

    Returns:
        完整扫描报告
    """
    directory = Path(directory)
    report = ScanReport()

    # Step 1: 扫描imports
    imports = scan_imports(directory)
    report.total_files = len(imports)
    report.imports = {k: {imp.module_name for imp in v} for k, v in imports.items()}
    report.total_imports = sum(len(v) for v in imports.values())

    # Step 2: 构建依赖图
    graph = build_dependency_graph(imports, base_package=base_package)

    # Step 3: 检测循环依赖
    report.cycles = detect_cycles(graph)

    # Step 4: 查找死代码
    report.dead_code = find_dead_code(directory, graph)

    # Step 5: 计算耦合度
    report.coupling = calc_coupling(graph)

    # Step 6: 统计函数和类数量
    for py_file in sorted(directory.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8-sig")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    report.total_functions += 1
                elif isinstance(node, ast.ClassDef):
                    report.total_classes += 1
        except (SyntaxError, UnicodeDecodeError):
            pass

    return report
