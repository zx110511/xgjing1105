import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

emb_path = Path(r"d:\元初系统\天机v9.1\indexing\embeddings.py")

print("=== M31 EmbeddingService v1.1 语法编译 ===")
try:
    py_compile.compile(str(emb_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(emb_path, "r", encoding="utf-8-sig") as f:
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
    "EmbeddingService类": "EmbeddingService" in classes,
    "__init__()": "__init__" in funcs,
    "_init_model()": "_init_model" in funcs,
    "_try_load_transformers()": "_try_load_transformers" in funcs,
    "_encode()": "_encode" in funcs,
    "_fallback_encode()": "_fallback_encode" in funcs,
    "_build_index()": "_build_index" in funcs,
    "rebuild_index()": "rebuild_index" in funcs,
    "semantic_search()": "semantic_search" in funcs,
    "get_index_stats()": "get_index_stats" in funcs,
    "add_to_index()": "add_to_index" in funcs,
    "remove_from_index()": "remove_from_index" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_embedding_effectiveness()": "_calc_embedding_effectiveness" in funcs,
    "_learn_from_embedding()": "_learn_from_embedding" in funcs,
    "_evolve_embedding_config()": "_evolve_embedding_config" in funcs,
    "D9-3 道谱溯源": "D9-3" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from core.processors.evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(rebuild_index)": 'action="rebuild_index"' in source,
    "record_action(semantic_search)": 'action="semantic_search"' in source,
    "record_action(add_to_index)": 'action="add_to_index"' in source,
}

print("\n=== M31 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)