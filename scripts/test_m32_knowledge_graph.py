import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

kg_path = Path(r"d:\元初系统\天机v9.1\indexing\knowledge_graph.py")

print("=== M32 KnowledgeGraph v1.1 语法编译 ===")
try:
    py_compile.compile(str(kg_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(kg_path, "r", encoding="utf-8-sig") as f:
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
    "KnowledgeGraph类": "KnowledgeGraph" in classes,
    "add_entity()": "add_entity" in funcs,
    "add_relation()": "add_relation" in funcs,
    "extract_from_text()": "extract_from_text" in funcs,
    "query_entity()": "query_entity" in funcs,
    "search_entities()": "search_entities" in funcs,
    "get_graph_stats()": "get_graph_stats" in funcs,
    "export_graph()": "export_graph" in funcs,
    "save()/_load()": "save" in funcs and "_load" in funcs,
    "_extract_named_entities()": "_extract_named_entities" in funcs,
    "_add_cooccurrence()": "_add_cooccurrence" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_kg_effectiveness()": "_calc_kg_effectiveness" in funcs,
    "_learn_from_kg()": "_learn_from_kg" in funcs,
    "_evolve_kg_config()": "_evolve_kg_config" in funcs,
    "D8-1 道谱溯源": "D8-1" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from core.processors.evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(extract_from_text)": 'action="extract_from_text"' in source,
    "record_action(add_entity)": 'action="add_entity"' in source,
    "record_action(add_relation)": 'action="add_relation"' in source,
    "record_action(query_entity)": 'action="query_entity"' in source,
}

print("\n=== M32 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)