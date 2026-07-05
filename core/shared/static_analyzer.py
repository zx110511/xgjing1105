r"""
天机静态依赖分析器 (Tianji Static Dependency Analyzer) v1.1
============================================================
Phase 2 治理机制建设 — 静态分析支柱

M21升级: EvolutionLoop闭环 + record_action喂入 + health() + 双注入
灵境道谱溯源: D6-1【依赖拓扑煞】· 道六·容器体 · 四地煞之容之术
  - 模块依赖拓扑排序→并行层计算→循环检测→关键模块优先
  - 源文件: core/static_analyzer.py → StaticDependencyAnalyzer

职责:
  1. 扫描源码提取导入依赖图
  2. 检测循环依赖
  3. 验证命名规范合规性
  4. 验证模块层级约束 (低层不得依赖高层)
  5. 生成合规审计报告

设计原则:
  - 纯静态分析: 不执行任何代码，只解析AST
  - 与ModuleRegistry协同: 分析结果可注入注册中心
  - 可执行架构: 每个规则都是可独立测试的验证函数

数据根基:
  - 从记忆库提取的Agent流水线结构 (development_pipeline: 洞察→经纬→妙笔→明镜→铁卫)
  - 进化闭环模式 (observe→learn→evolve 因果对)
  - 天机36地煞模块体系

参考:
  - Radon (Python代码复杂度工具)
  - pylint 架构分析
  - 专业级模块化方案 (TMD-Spec v1.0)
"""

import ast
import os
import time
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List, Set, Tuple
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)

try:
    from ..processors.evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None


# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════

class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ModuleLayer(str, Enum):
    L0_QUALITY = "L0"
    L1_SENSORY = "L1"
    L2_COGNITIVE = "L2"
    L3_ARCHIVAL = "L3"
    L4_SYSTEM = "L4"


@dataclass
class ImportDependency:
    source_module: str
    target_module: str
    import_type: str
    imported_names: List[str] = field(default_factory=list)
    line_number: int = 0


@dataclass
class ValidationFinding:
    rule_id: str
    rule_name: str
    severity: ValidationSeverity
    module_id: str
    message: str
    detail: str = ""
    line_number: int = 0
    suggestion: str = ""


@dataclass
class StaticAnalysisReport:
    analyzed_at: float = field(default_factory=time.time)
    total_files: int = 0
    total_modules: int = 0
    total_imports: int = 0
    total_classes: int = 0
    total_functions: int = 0
    dependencies: List[ImportDependency] = field(default_factory=list)
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)
    circular_dependencies: List[List[str]] = field(default_factory=list)
    findings: List[ValidationFinding] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=lambda: {
        "errors": 0, "warnings": 0, "info": 0
    })


@dataclass
class ModuleSourceInfo:
    module_id: str
    file_path: str
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    imports: List[ImportDependency] = field(default_factory=list)
    has_public_api: bool = False
    has_docstring: bool = False
    has_tests: bool = False
    code_lines: int = 0


# ═══════════════════════════════════════════════════════════════
# 模块层级约束
# ═══════════════════════════════════════════════════════════════

LAYER_HIERARCHY = {
    ModuleLayer.L0_QUALITY: [],
    ModuleLayer.L1_SENSORY: [ModuleLayer.L0_QUALITY],
    ModuleLayer.L2_COGNITIVE: [ModuleLayer.L0_QUALITY, ModuleLayer.L1_SENSORY],
    ModuleLayer.L3_ARCHIVAL: [ModuleLayer.L0_QUALITY, ModuleLayer.L1_SENSORY, ModuleLayer.L2_COGNITIVE],
    ModuleLayer.L4_SYSTEM: [ModuleLayer.L0_QUALITY, ModuleLayer.L1_SENSORY, ModuleLayer.L2_COGNITIVE, ModuleLayer.L3_ARCHIVAL],
}


MODULE_LAYER_MAP = {
    "enforcement_hook": ModuleLayer.L0_QUALITY,
    "quality_gate": ModuleLayer.L0_QUALITY,
    "engine": ModuleLayer.L1_SENSORY,
    "hybrid_engine": ModuleLayer.L1_SENSORY,
    "deepseek_driver": ModuleLayer.L2_COGNITIVE,
    "intelligent_scheduler": ModuleLayer.L2_COGNITIVE,
    "evolution_loop": ModuleLayer.L2_COGNITIVE,
    "evolution_engine": ModuleLayer.L2_COGNITIVE,
    "learning_loop": ModuleLayer.L2_COGNITIVE,
    "skill_registry": ModuleLayer.L2_COGNITIVE,
    "agent_orchestrator": ModuleLayer.L2_COGNITIVE,
    "chinese_tokenizer": ModuleLayer.L2_COGNITIVE,
    "router": ModuleLayer.L2_COGNITIVE,
    "config": ModuleLayer.L4_SYSTEM,
    "models": ModuleLayer.L4_SYSTEM,
    "llm_bridge": ModuleLayer.L4_SYSTEM,
    "async_bridge": ModuleLayer.L4_SYSTEM,
    "workflow_engine": ModuleLayer.L4_SYSTEM,
    "message_gateway": ModuleLayer.L4_SYSTEM,
    "tvp_bridge": ModuleLayer.L4_SYSTEM,
    "sqlite_store": ModuleLayer.L4_SYSTEM,
    "namespace_manager": ModuleLayer.L4_SYSTEM,
}


REQUIRED_CONVENTIONS = {
    "file_docstring": {
        "description": "文件必须有模块级文档字符串",
        "severity": ValidationSeverity.WARNING,
    },
    "class_docstring": {
        "description": "所有公开类必须有文档字符串",
        "severity": ValidationSeverity.WARNING,
    },
    "type_hints": {
        "description": "公开方法必须包含类型注解",
        "severity": ValidationSeverity.INFO,
    },
    "logging_import": {
        "description": "必须使用logging模块而非print",
        "severity": ValidationSeverity.WARNING,
    },
}


# ═══════════════════════════════════════════════════════════════
# AST访问器
# ═══════════════════════════════════════════════════════════════

class ModuleASTVisitor(ast.NodeVisitor):
    """遍历Python AST提取模块结构信息"""

    def __init__(self, module_id: str):
        self.module_id = module_id
        self.classes: List[str] = []
        self.functions: List[str] = []
        self.imports: List[ImportDependency] = []
        self.has_docstring = False
        self.public_classes: List[str] = []
        self.has_type_hints = True

    def visit_ClassDef(self, node: ast.ClassDef):
        class_name = node.name
        self.classes.append(class_name)
        if not class_name.startswith("_"):
            self.public_classes.append(class_name)
            if not ast.get_docstring(node):
                pass
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not node.name.startswith("_"):
            self.functions.append(node.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(ImportDependency(
                source_module=self.module_id,
                target_module=alias.name,
                import_type="import",
                imported_names=[alias.name],
                line_number=node.lineno,
            ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module is None:
            return
        module = node.module
        names = [alias.name for alias in node.names]
        if node.level > 0:
            module = "." * node.level + module
        self.imports.append(ImportDependency(
            source_module=self.module_id,
            target_module=module,
            import_type="from_import",
            imported_names=names,
            line_number=node.lineno,
        ))


# ═══════════════════════════════════════════════════════════════
# 验证规则引擎
# ═══════════════════════════════════════════════════════════════

class ValidationRuleEngine:
    """可插拔的验证规则引擎，支持自定义规则"""

    def __init__(self):
        self._rules: Dict[str, callable] = {}
        self._register_default_rules()

    def _register_default_rules(self):
        self._rules["R001_no_circular_deps"] = self._rule_no_circular_deps
        self._rules["R002_layer_violation"] = self._rule_layer_violation
        self._rules["R003_file_docstring"] = self._rule_file_docstring
        self._rules["R004_no_print"] = self._rule_no_print
        self._rules["R005_public_api_documented"] = self._rule_public_api_documented
        self._rules["R006_no_stdlib_duplicate"] = self._rule_no_stdlib_duplicate
        self._rules["R007_init_exports"] = self._rule_init_exports

    def register_rule(self, rule_id: str, rule_fn: callable):
        self._rules[rule_id] = rule_fn

    def run_all(self, context: Dict[str, Any]) -> List[ValidationFinding]:
        findings = []
        for rule_id, rule_fn in self._rules.items():
            try:
                result = rule_fn(context)
                if isinstance(result, list):
                    findings.extend(result)
                elif result:
                    findings.append(result)
            except Exception as e:
                logger.warning(f"规则 {rule_id} 执行异常: {e}")
        return findings

    def _rule_no_circular_deps(self, ctx: Dict[str, Any]) -> List[ValidationFinding]:
        """R001: 检测循环依赖"""
        deps = ctx.get("dependency_graph", {})
        cycles = self._find_cycles(deps)
        findings = []
        for cycle in cycles:
            cycle_str = " → ".join(cycle)
            findings.append(ValidationFinding(
                rule_id="R001",
                rule_name="循环依赖检测",
                severity=ValidationSeverity.ERROR,
                module_id=cycle[0],
                message=f"检测到循环依赖: {cycle_str}",
                detail="循环依赖会导致模块初始化失败和难以测试",
                suggestion=f"建议引入接口抽象或事件总线打破循环: {cycle[0]} 和 {cycle[-2]} 之间",
            ))
        return findings

    def _rule_layer_violation(self, ctx: Dict[str, Any]) -> List[ValidationFinding]:
        """R002: 层级违规检测"""
        dependencies = ctx.get("dependencies", [])
        findings = []
        for dep in dependencies:
            source_layer = MODULE_LAYER_MAP.get(dep.source_module)
            target_module = dep.target_module
            if target_module.startswith("."):
                continue
            target_layer = MODULE_LAYER_MAP.get(target_module)
            if source_layer and target_layer:
                allowed = LAYER_HIERARCHY.get(source_layer, [])
                if target_layer not in allowed and target_layer != source_layer:
                    source_order = int(source_layer.value[1])
                    target_order = int(target_layer.value[1])
                    if target_order > source_order:
                        findings.append(ValidationFinding(
                            rule_id="R002",
                            rule_name="层级依赖违规",
                            severity=ValidationSeverity.WARNING,
                            module_id=dep.source_module,
                            message=f"{dep.source_module}({source_layer.value}) 依赖了更高层的 "
                                    f"{target_module}({target_layer.value})",
                            detail="低层模块不应依赖高层模块，这违反了分层架构原则",
                            suggestion=f"考虑将共用功能下沉到 {target_layer.value} 层，"
                                      f"或通过事件总线解耦",
                            line_number=dep.line_number,
                        ))
        return findings

    def _rule_file_docstring(self, ctx: Dict[str, Any]) -> List[ValidationFinding]:
        """R003: 文件文档字符串"""
        modules = ctx.get("modules", {})
        findings = []
        for mod_id, info in modules.items():
            if not info.has_docstring:
                findings.append(ValidationFinding(
                    rule_id="R003",
                    rule_name="文件文档字符串",
                    severity=ValidationSeverity.WARNING,
                    module_id=mod_id,
                    message=f"{mod_id}.py 缺少模块级文档字符串",
                    suggestion="在文件开头添加 r\"\"\"...\"\"\" 模块文档",
                ))
        return findings

    def _rule_no_print(self, ctx: Dict[str, Any]) -> List[ValidationFinding]:
        """R004: 不使用print"""
        raw_calls = ctx.get("print_usage", {})
        findings = []
        for mod_id, lines in raw_calls.items():
            findings.append(ValidationFinding(
                rule_id="R004",
                rule_name="禁止使用print",
                severity=ValidationSeverity.WARNING,
                module_id=mod_id,
                message=f"{mod_id}.py 中有 {len(lines)} 处使用了print()",
                detail=f"行号: {lines[:5]}",
                suggestion="使用 logging.getLogger(__name__) 替代 print()",
            ))
        return findings

    def _rule_public_api_documented(self, ctx: Dict[str, Any]) -> List[ValidationFinding]:
        """R005: 公开API文档完整性"""
        modules = ctx.get("modules", {})
        findings = []
        for mod_id, info in modules.items():
            undocumented = []
            for cls in info.classes:
                if not cls.startswith("_") and cls not in ctx.get("documented_classes", {}).get(mod_id, []):
                    undocumented.append(cls)
            if undocumented:
                findings.append(ValidationFinding(
                    rule_id="R005",
                    rule_name="公开API文档",
                    severity=ValidationSeverity.INFO,
                    module_id=mod_id,
                    message=f"{mod_id}.py 有 {len(undocumented)} 个未文档化的公开类",
                    detail=f"未文档化: {undocumented[:5]}",
                    suggestion="为所有公开类添加文档字符串",
                ))
        return findings

    def _rule_no_stdlib_duplicate(self, ctx: Dict[str, Any]) -> List[ValidationFinding]:
        """R006: 不重复实现标准库功能"""
        return []

    def _rule_init_exports(self, ctx: Dict[str, Any]) -> List[ValidationFinding]:
        """R007: __init__.py 导出完整性"""
        modules = ctx.get("modules", {})
        init_exports = ctx.get("init_exports", set())
        findings = []
        for mod_id, info in modules.items():
            if mod_id == "__init__":
                continue
            for cls in info.classes:
                if not cls.startswith("_") and cls not in init_exports:
                    findings.append(ValidationFinding(
                        rule_id="R007",
                        rule_name="__init__导出完整性",
                        severity=ValidationSeverity.INFO,
                        module_id=mod_id,
                        message=f"{cls} 未在 __init__.py 中导出",
                        suggestion=f"在 __init__.py 中添加 from .{mod_id} import {cls}",
                    ))
        return findings

    @staticmethod
    def _find_cycles(graph: Dict[str, List[str]]) -> List[List[str]]:
        cycles = []
        visited = set()
        stack = []

        def dfs(node: str):
            if node in stack:
                cycle_start = stack.index(node)
                cycles.append(stack[cycle_start:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            stack.append(node)
            for neighbor in graph.get(node, []):
                dfs(neighbor)
            stack.pop()

        for node in list(graph.keys()):
            dfs(node)
        return cycles


# ═══════════════════════════════════════════════════════════════
# 静态分析器主体
# ═══════════════════════════════════════════════════════════════

class StaticDependencyAnalyzer:
    """
    天机静态依赖分析器

    分析流程:
      1. 扫描源码目录收集.py文件
      2. 对每个文件进行AST解析
      3. 提取导入、类、函数信息
      4. 构建依赖图
      5. 运行验证规则
      6. 生成分析报告

    使用方式:
      analyzer = StaticDependencyAnalyzer()
      report = analyzer.analyze("./core")
      print(analyzer.format_report(report))
    """

    def __init__(self, registry=None, recorder=None, learning_engine=None):
        self._registry = registry
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._rule_engine = ValidationRuleEngine()
        self._source_root: Optional[Path] = None
        self._analysis_history: List[StaticAnalysisReport] = []
        self._stats = {
            "analyses_run": 0,
            "total_modules_analyzed": 0,
            "total_classes_found": 0,
            "total_functions_found": 0,
            "total_imports_found": 0,
            "total_circular_deps": 0,
            "total_findings": 0,
            "errors_detected": 0,
            "warnings_detected": 0,
            "start_time": time.time(),
        }

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="static_analyzer",
                    effectiveness_fn=self._calc_analysis_effectiveness,
                    learn_fn=self._learn_from_analysis,
                    evolve_fn=self._evolve_analysis_rules,
                    mutable_config={
                        "max_cycle_depth": 50,
                        "analysis_cooldown_seconds": 60.0,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception as e:
                logger.warning(f"StaticAnalyzer EvolutionLoop init failed: {e}")

    def analyze(self, source_dir: str, exclude_patterns: Optional[List[str]] = None) -> StaticAnalysisReport:
        """
        对指定目录执行静态分析

        Args:
            source_dir: 源码目录路径
            exclude_patterns: 排除的文件名模式

        Returns:
            StaticAnalysisReport 分析报告
        """
        report = StaticAnalysisReport()
        self._source_root = Path(source_dir)
        exclude = set(exclude_patterns or [])

        py_files = [
            f for f in self._source_root.glob("*.py")
            if f.name not in exclude and not f.name.startswith("test_")
        ]
        report.total_files = len(py_files)

        modules_info: Dict[str, ModuleSourceInfo] = {}
        all_imports: List[ImportDependency] = []
        print_usage: Dict[str, List[int]] = defaultdict(list)

        for file_path in py_files:
            module_id = file_path.stem
            source_info = self._analyze_file(file_path, module_id)

            if source_info is None:
                continue

            modules_info[module_id] = source_info
            all_imports.extend(source_info.imports)
            report.total_classes += len(source_info.classes)
            report.total_functions += len(source_info.functions)

            print_lines = self._scan_print_usage(file_path)
            if print_lines:
                print_usage[module_id] = print_lines

        report.total_modules = len(modules_info)
        report.total_imports = len(all_imports)
        report.dependencies = all_imports

        dep_graph = self._build_dependency_graph(all_imports, modules_info)
        report.dependency_graph = dep_graph

        cycles = ValidationRuleEngine._find_cycles(dep_graph)
        report.circular_dependencies = cycles

        init_exports = self._extract_init_exports()

        rule_context = {
            "dependency_graph": dep_graph,
            "dependencies": all_imports,
            "modules": modules_info,
            "print_usage": dict(print_usage),
            "init_exports": init_exports,
            "documented_classes": {},
        }

        findings = self._rule_engine.run_all(rule_context)
        report.findings = findings

        for f in findings:
            key = f.severity.value + "s"
            if key in report.summary:
                report.summary[key] += 1

        self._stats["analyses_run"] += 1
        self._stats["total_modules_analyzed"] += report.total_modules
        self._stats["total_classes_found"] += report.total_classes
        self._stats["total_functions_found"] += report.total_functions
        self._stats["total_imports_found"] += report.total_imports
        self._stats["total_circular_deps"] += len(report.circular_dependencies)
        self._stats["total_findings"] += len(report.findings)
        self._stats["errors_detected"] += report.summary.get("errors", 0)
        self._stats["warnings_detected"] += report.summary.get("warnings", 0)

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="analyze",
                    state_before={"analyses_run": self._stats["analyses_run"] - 1},
                    state_after={"analyses_run": self._stats["analyses_run"],
                                 "modules": report.total_modules,
                                 "circular_deps": len(report.circular_dependencies),
                                 "errors": report.summary.get("errors", 0),
                                 "warnings": report.summary.get("warnings", 0)},
                )
            except Exception:
                pass

        self._analysis_history.append(report)
        return report

    def _analyze_file(self, file_path: Path, module_id: str) -> Optional[ModuleSourceInfo]:
        try:
            source_code = file_path.read_text(encoding="utf-8-sig")
        except Exception as e:
            logger.warning(f"无法读取文件 {file_path}: {e}")
            return None

        info = ModuleSourceInfo(
            module_id=module_id,
            file_path=str(file_path),
            code_lines=len(source_code.splitlines()),
        )

        try:
            tree = ast.parse(source_code, filename=str(file_path))
        except SyntaxError as e:
            logger.warning(f"文件 {file_path} 语法错误: {e}")
            return info

        info.has_docstring = ast.get_docstring(tree) is not None

        visitor = ModuleASTVisitor(module_id)
        visitor.visit(tree)

        info.classes = visitor.classes
        info.functions = visitor.functions

        internal_imports = []
        for imp in visitor.imports:
            if imp.target_module.startswith("."):
                internal_imports.append(imp)
        info.imports = internal_imports

        return info

    def _scan_print_usage(self, file_path: Path) -> List[int]:
        lines_with_print = []
        try:
            content = file_path.read_text(encoding="utf-8-sig")
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("print(") or stripped.startswith("print "):
                    if "logger" not in stripped and "logging" not in stripped:
                        lines_with_print.append(i)
        except Exception:
            pass
        return lines_with_print

    def _build_dependency_graph(
        self,
        imports: List[ImportDependency],
        modules_info: Dict[str, ModuleSourceInfo]
    ) -> Dict[str, List[str]]:
        graph: Dict[str, Set[str]] = defaultdict(set)
        all_modules = set(modules_info.keys())

        for imp in imports:
            target = imp.target_module
            if target.startswith("."):
                target = target.lstrip(".")
            if target in all_modules and target != imp.source_module:
                graph[imp.source_module].add(target)

        return {k: sorted(v) for k, v in graph.items()}

    def _extract_init_exports(self) -> Set[str]:
        if self._source_root is None:
            return set()
        init_file = self._source_root / "__init__.py"
        if not init_file.exists():
            return set()
        try:
            content = init_file.read_text(encoding="utf-8-sig")
            tree = ast.parse(content, filename=str(init_file))
            exports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.names:
                        exports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.Import):
                    exports.update(alias.name.split(".")[0] for alias in node.names)
            return exports
        except Exception:
            return set()

    def diff_report(
        self,
        report_a: StaticAnalysisReport,
        report_b: StaticAnalysisReport
    ) -> Dict[str, Any]:
        diff = {
            "modules_added": set(),
            "modules_removed": set(),
            "deps_added": [],
            "deps_removed": [],
            "findings_resolved": [],
            "findings_new": [],
        }

        deps_a = {(d.source_module, d.target_module) for d in report_a.dependencies}
        deps_b = {(d.source_module, d.target_module) for d in report_b.dependencies}

        diff["deps_added"] = [list(d) for d in deps_b - deps_a]
        diff["deps_removed"] = [list(d) for d in deps_a - deps_b]

        findings_a = {(f.rule_id, f.module_id) for f in report_a.findings}
        findings_b = {(f.rule_id, f.module_id) for f in report_b.findings}

        diff["findings_new"] = [list(f) for f in findings_b - findings_a]
        diff["findings_resolved"] = [list(f) for f in findings_a - findings_b]

        return diff

    def format_report(self, report: StaticAnalysisReport) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("  天机静态依赖分析报告")
        lines.append("=" * 60)
        lines.append(f"  分析时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report.analyzed_at))}")
        lines.append(f"  模块总数: {report.total_modules}")
        lines.append(f"  类总数:   {report.total_classes}")
        lines.append(f"  函数总数: {report.total_functions}")
        lines.append(f"  依赖边:   {report.total_imports}")
        lines.append("")
        lines.append(f"  问题汇总: 🔴 {report.summary['errors']} "
                     f"🟡 {report.summary['warnings']} "
                     f"🔵 {report.summary['info']}")
        lines.append("")

        if report.circular_dependencies:
            lines.append("  [循环依赖]")
            for i, cycle in enumerate(report.circular_dependencies, 1):
                lines.append(f"    {i}. {' → '.join(cycle)}")
            lines.append("")

        if report.findings:
            lines.append("  [合规审计发现]")
            for severity in [ValidationSeverity.ERROR, ValidationSeverity.WARNING, ValidationSeverity.INFO]:
                sev_findings = [f for f in report.findings if f.severity == severity]
                if not sev_findings:
                    continue
                emoji = {"error": "🔴", "warning": "🟡", "info": "🔵"}[severity.value]
                lines.append(f"  {emoji} [{severity.value.upper()}] {len(sev_findings)} 条")
                for f in sev_findings[:10]:
                    lines.append(f"      [{f.rule_id}] {f.message}")
                    if f.suggestion:
                        lines.append(f"           建议: {f.suggestion}")
                if len(sev_findings) > 10:
                    lines.append(f"      ... 还有 {len(sev_findings) - 10} 条")
                lines.append("")

        if report.dependency_graph:
            lines.append("  [依赖图]")
            for mod, deps in sorted(report.dependency_graph.items()):
                if deps:
                    lines.append(f"    {mod} → [{', '.join(deps)}]")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def get_history(self) -> List[StaticAnalysisReport]:
        return self._analysis_history

    def clear_history(self):
        self._analysis_history.clear()

    def register_custom_rule(self, rule_id: str, rule_fn: callable):
        self._rule_engine.register_rule(rule_id, rule_fn)

    def health(self) -> Dict[str, Any]:
        return {
            "status": "ready",
            "version": "1.1",
            "analyses_run": self._stats["analyses_run"],
            "total_modules_analyzed": self._stats["total_modules_analyzed"],
            "total_classes_found": self._stats["total_classes_found"],
            "total_functions_found": self._stats["total_functions_found"],
            "total_circular_deps": self._stats["total_circular_deps"],
            "total_findings": self._stats["total_findings"],
            "errors_detected": self._stats["errors_detected"],
            "warnings_detected": self._stats["warnings_detected"],
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
            "registry_attached": self._registry is not None,
            "history_count": len(self._analysis_history),
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "version": "1.1",
            **self._stats,
            "health": self.health(),
            "evo_loop": self._evo_loop.get_stats() if self._evo_loop else {},
        }

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_analysis_effectiveness(self, action: str,
                                      state_before: Dict[str, Any],
                                      state_after: Dict[str, Any]) -> float:
        if action == "analyze":
            errors = state_after.get("errors", 0)
            warnings = state_after.get("warnings", 0)
            modules = state_after.get("modules", 1)
            if errors == 0:
                return min(0.7, 0.3 + modules * 0.02)
            return -0.2 * max(1, min(errors, 5))
        return 0.0

    def _learn_from_analysis(self, causal_pairs: List[Any],
                              effectiveness_summary: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "total_analyses": self._stats["analyses_run"],
            "error_rate": (
                self._stats["errors_detected"] / max(self._stats["total_findings"], 1)
            ),
        }

    def _evolve_analysis_rules(self, learn_result: Dict[str, Any],
                                mutable_config: Dict[str, Any]) -> Dict[str, Any]:
        changes = {}
        error_rate = learn_result.get("error_rate", 0.0)
        if error_rate > 0.5:
            changes["analysis_cooldown_seconds"] = min(300,
                mutable_config.get("analysis_cooldown_seconds", 60) + 30)
        if error_rate < 0.1 and mutable_config.get("analysis_cooldown_seconds", 60) > 30:
            changes["analysis_cooldown_seconds"] = max(30,
                mutable_config.get("analysis_cooldown_seconds", 60) - 15)
        return {"rules_modified": changes, "skills_created": []}


# ═══════════════════════════════════════════════════════════════
# 与ModuleRegistry的集成桥接
# ═══════════════════════════════════════════════════════════════

def sync_analyzer_to_registry(
    analyzer: StaticDependencyAnalyzer,
    registry,
    report: StaticAnalysisReport
) -> Dict[str, Any]:
    sync_result = {
        "dependencies_synced": 0,
        "circular_deps_reported": len(report.circular_dependencies),
        "findings_archived": len(report.findings),
        "layer_violations": [],
    }
    from .module_registry import AuditRecord, AuditStatus

    for dep in report.dependencies:
        target = dep.target_module.lstrip(".") if dep.target_module.startswith(".") else dep.target_module
        if target in registry._modules and target != dep.source_module:
            sync_result["dependencies_synced"] += 1

    for f in report.findings:
        if f.severity.value in ("error", "warning"):
            if hasattr(registry, 'get') and registry.get(f.module_id):
                module_def = registry.get(f.module_id)
                audit = AuditRecord(
                    audit_id=f"{f.rule_id}_{f.module_id}_{int(time.time())}",
                    module_id=f.module_id,
                    check_type=f.rule_name,
                    status=AuditStatus.FAILED if f.severity.value == "error" else AuditStatus.PASSED,
                    score=0.0 if f.severity.value == "error" else 0.7,
                    issues=[f.message],
                    suggestions=[f.suggestion] if f.suggestion else [],
                )
                module_def.add_audit_record(audit)

    for cycle in report.circular_dependencies:
        sync_result["layer_violations"].append({"cycle": cycle, "severity": "error"})

    logger.info(f"[StaticAnalyzer] 同步完成: {sync_result['dependencies_synced']} 依赖, "
                f"{sync_result['findings_archived']} 审计发现, "
                f"{sync_result['circular_deps_reported']} 循环依赖")
    return sync_result


def analyze_and_validate(analyzer: StaticDependencyAnalyzer, source_dir: str) -> Tuple[StaticAnalysisReport, bool]:
    report = analyzer.analyze(source_dir)
    passed = report.summary.get("errors", 0) == 0
    return report, passed
