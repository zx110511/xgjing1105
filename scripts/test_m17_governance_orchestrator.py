import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

go_path = Path(r"d:\元初系统\天机v9.1\core\governance_orchestrator.py")

print("=== M17 GovernanceOrchestrator v1.1 语法编译 ===")
try:
    py_compile.compile(str(go_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(go_path, "r", encoding="utf-8-sig") as f:
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
    "GovernanceOrchestrator类": "GovernanceOrchestrator" in classes,
    "bootstrap()": "bootstrap" in funcs,
    "_run_registration_phase()": "_run_registration_phase" in funcs,
    "_run_analysis_phase()": "_run_analysis_phase" in funcs,
    "_run_pipeline_phase()": "_run_pipeline_phase" in funcs,
    "_generate_audit_report()": "_generate_audit_report" in funcs,
    "get_status()": "get_status" in funcs,
    "health_check_all()": "health_check_all" in funcs,
    "export_module_manifest()": "export_module_manifest" in funcs,
    "run_reaudit()": "run_reaudit" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_orchestrator_effectiveness()": "_calc_orchestrator_effectiveness" in funcs,
    "_learn_from_orchestrator()": "_learn_from_orchestrator" in funcs,
    "_evolve_orchestrator_config()": "_evolve_orchestrator_config" in funcs,
    "D4-1 道谱溯源": "D4-1" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(bootstrap)": 'action="bootstrap"' in source,
    "record_action(register)": 'action="register"' in source,
    "record_action(analyze)": 'action="analyze"' in source,
    "record_action(pipeline)": 'action="pipeline"' in source,
}

print("\n=== M17 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)