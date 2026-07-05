import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

daemon_path = Path(r"d:\元初系统\天机v9.1\daemon\tianji_daemon.py")

print("=== M30 TianjiDaemon v9.1 语法编译 ===")
try:
    py_compile.compile(str(daemon_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(daemon_path, "r", encoding="utf-8-sig") as f:
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
print(f"    Functions: {len(funcs)}")

checks = {
    "TianjiDaemon类": "TianjiDaemon" in classes,
    "Watchdog类": "Watchdog" in classes,
    "AutoBackup类": "AutoBackup" in classes,
    "AutoRepair类": "AutoRepair" in classes,
    "IntegrityChecker类": "IntegrityChecker" in classes,
    "run()": "run" in funcs,
    "stop()": "stop" in funcs,
    "status()": "status" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_daemon_effectiveness()": "_calc_daemon_effectiveness" in funcs,
    "_learn_from_daemon()": "_learn_from_daemon" in funcs,
    "_evolve_daemon_config()": "_evolve_daemon_config" in funcs,
    "_check_health()": "_check_health" in funcs,
    "_start_server()": "_start_server" in funcs,
    "_stop_server()": "_stop_server" in funcs,
    "Watchdog.check()": "check" in funcs,
    "AutoBackup.incremental()": "incremental" in funcs,
    "AutoBackup.full()": "full" in funcs,
    "AutoRepair.diagnose_and_repair()": "diagnose_and_repair" in funcs,
    "IntegrityChecker.check()": "check" in funcs,
    "D7-1 道谱溯源": "D7-1" in source,
    "v9.1 docstring": "v9.1" in source,
    "EvolutionLoop灵活导入": "from core.processors.evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(daemon_loop)": 'action="daemon_loop"' in source,
    "SYSTEM_VERSION 8.1": '"9.0"' in source,
    "四级容器守护架构": "四级容器守护架构" in source,
}

print("\n=== M30 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)