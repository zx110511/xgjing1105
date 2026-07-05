import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

rp = Path(r"d:\元初系统\天机v9.1\core\router.py")

print("=== M22 LayerRouter v1.1 语法编译 ===")
try:
    py_compile.compile(str(rp), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(rp, "r", encoding="utf-8-sig") as f:
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
print(f"    Methods: {len(funcs)}")

checks = {
    "LayerRouter类": "LayerRouter" in classes,
    "MemoryLayer枚举": "MemoryLayer" in classes,
    "TargetSystem枚举": "TargetSystem" in classes,
    "RoutingRule数据类": "RoutingRule" in classes,
    "get_target()": "get_target" in funcs,
    "route()": "route" in funcs,
    "split_query()": "split_query" in funcs,
    "update_external_health()": "update_external_health" in funcs,
    "_check_external_health()": "_check_external_health" in funcs,
    "get_degradation_log()": "get_degradation_log" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_router_effectiveness()": "_calc_router_effectiveness" in funcs,
    "_learn_from_router()": "_learn_from_router" in funcs,
    "_evolve_router_config()": "_evolve_router_config" in funcs,
    "D5-3 道谱溯源": "D5-3" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(update_external_health)": 'action="update_external_health"' in source,
    "record_action(route)": 'action="route"' in source,
    "record_action(split_query)": 'action="split_query"' in source,
    "stats(route_ops)": '"route_ops"' in source,
    "stats(split_ops)": '"split_ops"' in source,
    "stats(health_checks)": '"health_checks"' in source,
    "stats(degradation_events)": '"degradation_events"' in source,
}

print("\n=== M22 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)
