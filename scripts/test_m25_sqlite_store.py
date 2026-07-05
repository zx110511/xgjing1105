import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

ss_path = Path(r"d:\元初系统\天机v9.1\core\sqlite_store.py")

print("=== M25 SQLiteMemoryStore v1.1 语法编译 ===")
try:
    py_compile.compile(str(ss_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(ss_path, "r", encoding="utf-8-sig") as f:
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
    "SQLiteMemoryStore": "SQLiteMemoryStore" in classes,
    "StorageStats": "StorageStats" in classes,
    "SCHEMA_VERSION": "SCHEMA_VERSION" in source,
    "__init__()": "__init__" in funcs,
    "_init_db()": "_init_db" in funcs,
    "_get_conn()": "_get_conn" in funcs,
    "insert()": "insert" in funcs,
    "insert_batch()": "insert_batch" in funcs,
    "get()": "get" in funcs,
    "search()": "search" in funcs,
    "search_by_tags()": "search_by_tags" in funcs,
    "update()": "update" in funcs,
    "delete()": "delete" in funcs,
    "vacuum()": "vacuum" in funcs,
    "get_storage_stats()": "get_storage_stats" in funcs,
    "get_total_stats()": "get_total_stats" in funcs,
    "get_layer_stats()": "get_layer_stats" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_store_effectiveness()": "_calc_store_effectiveness" in funcs,
    "_learn_from_store()": "_learn_from_store" in funcs,
    "_evolve_store_config()": "_evolve_store_config" in funcs,
    "D1-3 道谱溯源": "D1-3" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(insert)": 'action="insert"' in source,
    "record_action(insert_batch)": 'action="insert_batch"' in source,
    "record_action(search)": 'action="search"' in source,
    "record_action(vacuum)": 'action="vacuum"' in source,
    "stats(insert_ops)": '"insert_ops"' in source,
    "stats(batch_ops)": '"batch_ops"' in source,
    "stats(search_ops)": '"search_ops"' in source,
}

print("\n=== M25 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)
