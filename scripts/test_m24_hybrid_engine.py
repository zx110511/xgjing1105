import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

hy_path = Path(r"d:\元初系统\天机v9.1\core\hybrid_engine.py")

print("=== M24 HybridStorageEngine v1.1 语法编译 ===")
try:
    py_compile.compile(str(hy_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(hy_path, "r", encoding="utf-8-sig") as f:
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
    "ICMEStorageEngine类": "ICMEStorageEngine" in classes,
    "__init__()": "__init__" in funcs,
    "_ensure_dirs()": "_ensure_dirs" in funcs,
    "_migrate_json_to_sqlite()": "_migrate_json_to_sqlite" in funcs,
    "remember()": "remember" in funcs,
    "remember_batch()": "remember_batch" in funcs,
    "recall()": "recall" in funcs,
    "forget()": "forget" in funcs,
    "consolidate()": "consolidate" in funcs,
    "stats()": "stats" in funcs,
    "get_layer_capacity_info()": "get_layer_capacity_info" in funcs,
    "full_text_search()": "full_text_search" in funcs,
    "build_export_data()": "build_export_data" in funcs,
    "vacuum()": "vacuum" in funcs,
    "close()": "close" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_hybrid_effectiveness()": "_calc_hybrid_effectiveness" in funcs,
    "_learn_from_hybrid()": "_learn_from_hybrid" in funcs,
    "_evolve_hybrid_config()": "_evolve_hybrid_config" in funcs,
    "D1-2 道谱溯源": "D1-2" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(remember)": 'action="remember"' in source,
    "record_action(remember_batch)": 'action="remember_batch"' in source,
    "record_action(recall)": 'action="recall"' in source,
    "record_action(consolidate)": 'action="consolidate"' in source,
}

print("\n=== M24 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)