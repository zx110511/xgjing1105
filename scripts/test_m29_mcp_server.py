import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

mcp_path = Path(r"d:\元初系统\天机v9.1\mcp\tianji_mcp_server.py")

print("=== M29 MCPServer v9.1 语法编译 ===")
try:
    py_compile.compile(str(mcp_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(mcp_path, "r", encoding="utf-8-sig") as f:
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
    "TianjiMCPServer类": "TianjiMCPServer" in classes,
    "_check_api()": "_check_api" in funcs,
    "_api_post()": "_api_post" in funcs,
    "_api_get()": "_api_get" in funcs,
    "_make_response()": "_make_response" in funcs,
    "handle_initialize()": "handle_initialize" in funcs,
    "handle_tools_list()": "handle_tools_list" in funcs,
    "handle_tools_call()": "handle_tools_call" in funcs,
    "run()": "run" in funcs,
    "_handle_remember()": "_handle_remember" in funcs,
    "_handle_recall()": "_handle_recall" in funcs,
    "_handle_stats()": "_handle_stats" in funcs,
    "_handle_health()": "_handle_health" in funcs,
    "_handle_help()": "_handle_help" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_mcp_effectiveness()": "_calc_mcp_effectiveness" in funcs,
    "_learn_from_mcp()": "_learn_from_mcp" in funcs,
    "_evolve_mcp_config()": "_evolve_mcp_config" in funcs,
    "D1-4 道谱溯源": "D1-4" in source,
    "v9.1 docstring": "v9.1" in source,
    "EvolutionLoop灵活导入": "from core.processors.evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(health_check)": 'action="health_check"' in source,
    "record_action(handle_initialize)": 'action="handle_initialize"' in source,
    "record_action(tool_call)": 'action="tool_call"' in source,
}

print("\n=== M29 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)