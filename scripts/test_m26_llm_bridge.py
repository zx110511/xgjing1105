import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

lb_path = Path(r"d:\元初系统\天机v9.1\core\llm_bridge.py")

print("=== M26 LLMBridge v1.1 语法编译 ===")
try:
    py_compile.compile(str(lb_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(lb_path, "r", encoding="utf-8-sig") as f:
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
    "LLMBridge类": "LLMBridge" in classes,
    "__init__()": "__init__" in funcs,
    "_init()": "_init" in funcs,
    "_call_llm()": "_call_llm" in funcs,
    "is_ready property": "is_ready" in source,
    "classify_content()": "classify_content" in funcs,
    "auto_tag()": "auto_tag" in funcs,
    "assess_value()": "assess_value" in funcs,
    "decide_storage()": "decide_storage" in funcs,
    "extract_knowledge()": "extract_knowledge" in funcs,
    "summarize()": "summarize" in funcs,
    "expand_query()": "expand_query" in funcs,
    "enrich_remember()": "enrich_remember" in funcs,
    "enrich_recall()": "enrich_recall" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_bridge_effectiveness()": "_calc_bridge_effectiveness" in funcs,
    "_learn_from_bridge()": "_learn_from_bridge" in funcs,
    "_evolve_bridge_config()": "_evolve_bridge_config" in funcs,
    "D9-4 道谱溯源": "D9-4" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(enrich_remember)": 'action="enrich_remember"' in source,
    "record_action(enrich_recall)": 'action="enrich_recall"' in source,
    "stats扩展(classify_ops)": '"classify_ops"' in source,
    "stats扩展(enrich_remember_ops)": '"enrich_remember_ops"' in source,
    "stats扩展(enrich_recall_ops)": '"enrich_recall_ops"' in source,
}

print("\n=== M26 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)
