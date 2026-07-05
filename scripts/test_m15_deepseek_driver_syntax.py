import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

driver_path = Path(r"d:\元初系统\天机v9.1\core\deepseek_driver.py")

print("=== M15 DeepSeekDriver v2.2 语法编译 ===")
try:
    py_compile.compile(str(driver_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(driver_path, "r", encoding="utf-8-sig") as f:
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
    "DeepSeekDriver": "DeepSeekDriver" in classes,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "_calc_driver_effectiveness": "_calc_driver_effectiveness" in funcs,
    "_learn_from_driver": "_learn_from_driver" in funcs,
    "_evolve_driver_config": "_evolve_driver_config" in funcs,
    "_deep_think_cycle": "_deep_think_cycle" in funcs,
    "_evolution_cycle": "_evolution_cycle" in funcs,
    "act()": "act" in funcs,
    "trigger_deep_think": "trigger_deep_think" in funcs,
    "trigger_evolution": "trigger_evolution" in funcs,
    "register_module_loop": "register_module_loop" in funcs,
    "perceive()": "perceive" in funcs,
    "start()": "start" in funcs,
    "stop()": "stop" in funcs,
    "_main_loop()": "_main_loop" in funcs,
    "v2.2 docstring": "v2.2" in source,
    "道谱溯源": "D2-1" in source,
    "record_action喂入(act)": "driver_act" in source,
    "record_action喂入(deep_think)": "deep_think_cycle" in source and "evo_loop.record_action" in source,
    "record_action喂入(evolution)": "evolution_cycle" in source and "\"evolution_cycle\"" in source,
    "recorder双注入": "_recorder = recorder" in source,
    "learning_engine双注入": "_shared_learning_engine = learning_engine" in source,
    "EvolutionLoop初始化": "EvolutionLoopShared" in source or "self._evo_loop" in source,
    "evo_loop.tick()主循环": "self._evo_loop.tick()" in source,
    "health返回version 2.2": '"version": "2.2"' in source,
}

print("\n=== M15 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)
