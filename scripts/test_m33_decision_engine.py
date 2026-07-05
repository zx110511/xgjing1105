import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

de_path = Path(r"d:\元初系统\天机v9.1\llm_integration\decision_engine.py")

print("=== M33 DeepSeekDecisionEngine v9.1 语法编译 ===")
try:
    py_compile.compile(str(de_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(de_path, "r", encoding="utf-8-sig") as f:
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
    "ClassificationResult": "ClassificationResult" in classes,
    "StorageDecision": "StorageDecision" in classes,
    "MemoryDecisionEngine": "MemoryDecisionEngine" in classes,
    "classify_layer()": "classify_layer" in funcs,
    "_do_classify()": "_do_classify" in funcs,
    "auto_tag()": "auto_tag" in funcs,
    "_do_auto_tag()": "_do_auto_tag" in funcs,
    "assess_value()": "assess_value" in funcs,
    "extract_knowledge()": "extract_knowledge" in funcs,
    "_do_extract_knowledge()": "_do_extract_knowledge" in funcs,
    "summarize()": "summarize" in funcs,
    "decide_storage()": "decide_storage" in funcs,
    "expand_query()": "expand_query" in funcs,
    "search_relevance()": "search_relevance" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_engine_effectiveness": "_calc_engine_effectiveness" in funcs,
    "_learn_from_decisions": "_learn_from_decisions" in funcs,
    "_evolve_decision_params": "_evolve_decision_params" in funcs,
    "D8-2 道谱溯源": "D8-2" in source,
    "v9.1 docstring": "v9.1" in source,
    "EvolutionLoop灵活导入": "from core.processors.evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "_recorder = recorder" in source,
    "learning_engine双注入": "_learning_engine = learning_engine" in source,
    "record_action(classify_layer)": 'action="classify_layer"' in source,
    "record_action(extract_knowledge)": 'action="extract_knowledge"' in source,
    "record_action(decide_storage)": 'action="decide_storage"' in source,
    "record_action(auto_tag)": 'action="auto_tag"' in source,
    "stats追踪(classify_calls)": '"classify_calls"' in source,
}

print("\n=== M33 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)
