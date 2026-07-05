import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

ns_path = Path(r"d:\元初系统\天机v9.1\core\namespace_manager.py")

print("=== M23 NamespaceManager v1.1 语法编译 ===")
try:
    py_compile.compile(str(ns_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(ns_path, "r", encoding="utf-8-sig") as f:
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
    "NamespaceManager类": "NamespaceManager" in classes,
    "AgentNamespace dataclass": "AgentNamespace" in classes,
    "PerspectiveKey dataclass": "PerspectiveKey" in classes,
    "__init__()": "__init__" in funcs,
    "_init_default_namespaces()": "_init_default_namespaces" in funcs,
    "get_or_create()": "get_or_create" in funcs,
    "get()": "get" in funcs,
    "list_all()": "list_all" in funcs,
    "list_active()": "list_active" in funcs,
    "deactivate()": "deactivate" in funcs,
    "activate()": "activate" in funcs,
    "increment_memory()": "increment_memory" in funcs,
    "stats()": "stats" in funcs,
    "get_namespace_for_agent()": "get_namespace_for_agent" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_ns_effectiveness()": "_calc_ns_effectiveness" in funcs,
    "_learn_from_ns()": "_learn_from_ns" in funcs,
    "_evolve_ns_config()": "_evolve_ns_config" in funcs,
    "D8-3 道谱溯源": "D8-3" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(get_or_create)": 'action="get_or_create"' in source,
    "record_action(deactivate)": 'action="deactivate"' in source,
    "record_action(activate)": 'action="activate"' in source,
    "record_action(increment_memory)": 'action="increment_memory"' in source,
}

print("\n=== M23 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)