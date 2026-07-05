import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

sa_path = Path(r"d:\元初系统\天机v9.1\core\static_analyzer.py")

print("=== M21 StaticAnalyzer v1.1 语法编译 ===")
try:
    py_compile.compile(str(sa_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(sa_path, "r", encoding="utf-8-sig") as f:
    source = f.read()

try:
    tree = ast.parse(source)
    print(f"✅ AST parse: PASS ({len(tree.body)} top-level nodes)")
except SyntaxError as e:
    print(f"❌ AST parse: FAIL — {e}")
    sys.exit(1)

classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

print(f"    Classes: {len(classes)} — {classes}")
print(f"    Functions/Methods: {len(funcs)}")

checks = {
    "StaticDependencyAnalyzer": "StaticDependencyAnalyzer" in classes,
    "ValidationRuleEngine": "ValidationRuleEngine" in classes,
    "ModuleASTVisitor": "ModuleASTVisitor" in classes,
    "ValidationSeverity枚举": "ValidationSeverity" in classes,
    "ModuleLayer枚举": "ModuleLayer" in classes,
    "StaticAnalysisReport": "StaticAnalysisReport" in classes,
    "analyze()": "analyze" in funcs,
    "format_report()": "format_report" in funcs,
    "diff_report()": "diff_report" in funcs,
    "get_history()": "get_history" in funcs,
    "clear_history()": "clear_history" in funcs,
    "register_custom_rule()": "register_custom_rule" in funcs,
    "_analyze_file()": "_analyze_file" in funcs,
    "_scan_print_usage()": "_scan_print_usage" in funcs,
    "_build_dependency_graph()": "_build_dependency_graph" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_analysis_effectiveness()": "_calc_analysis_effectiveness" in funcs,
    "_learn_from_analysis()": "_learn_from_analysis" in funcs,
    "_evolve_analysis_rules()": "_evolve_analysis_rules" in funcs,
    "D6-1 道谱溯源": "D6-1" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(analyze)": 'action="analyze"' in source,
    "sync_analyzer_to_registry()": "sync_analyzer_to_registry" in funcs,
    "analyze_and_validate()": "analyze_and_validate" in funcs,
}

print("\n=== M21 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)
