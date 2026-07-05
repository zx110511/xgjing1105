import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

evo_path = Path(r"d:\元初系统\天机v9.1\core\evolution_loop.py")

print("=== M35 EvolutionBus v9.1 语法编译 ===")
try:
    py_compile.compile(str(evo_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(evo_path, "r", encoding="utf-8-sig") as f:
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
print(f"    Methods/Functions: {len(funcs)}")

checks = {
    "EvolutionBus类": "EvolutionBus" in classes,
    "EvolutionLoop类": "EvolutionLoop" in classes,
    "CausalPairRecorder类": "CausalPairRecorder" in classes,
    "ModuleChallenger类": "ModuleChallenger" in classes,
    "register_loop()": "register_loop" in funcs,
    "_route_signal()": "_route_signal" in funcs,
    "get_stats()": "get_stats" in funcs,
    "get_signal_history()": "get_signal_history" in funcs,
    "health()": "health" in funcs,
    "get_full_stats()": "get_full_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_bus_effectiveness()": "_calc_bus_effectiveness" in funcs,
    "_learn_from_bus()": "_learn_from_bus" in funcs,
    "_evolve_bus_routing()": "_evolve_bus_routing" in funcs,
    "ROUTING_TABLE 9信号类型": "GATE_MISJUDGMENT" in source and "SKILL_UNDERUSE" in source and "CAPACITY_PRESSURE" in source,
    "D3-4 道谱溯源": "D3-4" in source,
    "D6-3 道谱溯源": "D6-3" in source,
    "v9.1 docstring": "v9.1" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(register_loop)": 'action="register_loop"' in source,
    "record_action(route_signal)": 'action="route_signal"' in source,
    "模式发现煞": "模式发现煞" in source,
    "事件总线煞": "事件总线煞" in source,
}

print("\n=== M35 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)