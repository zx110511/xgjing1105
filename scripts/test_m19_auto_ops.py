import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

ops_path = Path(r"d:\元初系统\天机v9.1\core\auto_ops.py")

print("=== M19 AutoOpsEngine v1.1 语法编译 ===")
try:
    py_compile.compile(str(ops_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(ops_path, "r", encoding="utf-8-sig") as f:
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
    "AutoHealer类": "AutoHealer" in classes,
    "BaselineEngine类": "BaselineEngine" in classes,
    "AutoOpsCoordinator类": "AutoOpsCoordinator" in classes,
    "HealingRecord dataclass": "HealingRecord" in classes,
    "MetricSnapshot dataclass": "MetricSnapshot" in classes,
    "AnomalyReport dataclass": "AnomalyReport" in classes,
    "ScaleRecommendation dataclass": "ScaleRecommendation" in classes,
    "AutoHealer.heal()": "heal" in funcs,
    "AutoHealer.get_stats()": "get_stats" in funcs,
    "BaselineEngine.record_metric()": "record_metric" in funcs,
    "BaselineEngine.detect_anomalies()": "detect_anomalies" in funcs,
    "BaselineEngine.generate_scale_recommendation()": "generate_scale_recommendation" in funcs,
    "AutoOpsCoordinator.__init__()": "__init__" in funcs,
    "AutoOpsCoordinator.start()": "start" in funcs,
    "AutoOpsCoordinator.stop()": "stop" in funcs,
    "AutoOpsCoordinator.generate_ops_report()": "generate_ops_report" in funcs,
    "AutoOpsCoordinator.trigger_manual_heal()": "trigger_manual_heal" in funcs,
    "health()": "health" in funcs,
    "tick()": "tick" in funcs,
    "_calc_ops_effectiveness()": "_calc_ops_effectiveness" in funcs,
    "_learn_from_ops()": "_learn_from_ops" in funcs,
    "_evolve_ops_config()": "_evolve_ops_config" in funcs,
    "D4-2 道谱溯源": "D4-2" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(handle_evolution_signal)": 'action="handle_evolution_signal"' in source,
    "record_action(monitoring_cycle)": 'action="monitoring_cycle"' in source,
    "record_action(generate_ops_report)": 'action="generate_ops_report"' in source,
}

print("\n=== M19 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)