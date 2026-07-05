import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

mr_path = Path(r"d:\元初系统\天机v9.1\core\module_registry.py")

print("=== M20 ModuleRegistry v1.1 语法编译 ===")
try:
    py_compile.compile(str(mr_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(mr_path, "r", encoding="utf-8-sig") as f:
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
    "ModuleRegistry类": "ModuleRegistry" in classes,
    "ModuleLifecycleState枚举": "ModuleLifecycleState" in classes,
    "ModuleTier枚举": "ModuleTier" in classes,
    "TianjiModuleDefinition": "TianjiModuleDefinition" in classes,
    "register()": "register" in funcs,
    "unregister()": "unregister" in funcs,
    "get()": "get" in funcs,
    "bind_instance()": "bind_instance" in funcs,
    "get_dependencies()": "get_dependencies" in funcs,
    "get_dependents()": "get_dependents" in funcs,
    "find_circular_dependencies()": "find_circular_dependencies" in funcs,
    "get_module_graph()": "get_module_graph" in funcs,
    "get_stats()": "get_stats" in funcs,
    "get_unified_stats()": "get_unified_stats" in funcs,
    "validate_dependencies()": "validate_dependencies" in funcs,
    "health_check_all()": "health_check_all" in funcs,
    "export_module_manifest()": "export_module_manifest" in funcs,
    "health()": "health" in funcs,
    "tick()": "tick" in funcs,
    "_calc_registry_effectiveness()": "_calc_registry_effectiveness" in funcs,
    "_learn_from_registry()": "_learn_from_registry" in funcs,
    "_evolve_registry_config()": "_evolve_registry_config" in funcs,
    "D6-2 道谱溯源": "D6-2" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(register)": 'action="register_module"' in source,
    "record_action(unregister)": 'action="unregister_module"' in source,
    "record_action(bind_instance)": 'action="bind_instance"' in source,
}

print("\n=== M20 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)
