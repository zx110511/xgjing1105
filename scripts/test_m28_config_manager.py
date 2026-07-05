import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

cfg_path = Path(r"d:\元初系统\天机v9.1\core\config.py")

print("=== M28 ConfigManager v9.1 语法编译 ===")
try:
    py_compile.compile(str(cfg_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(cfg_path, "r", encoding="utf-8-sig") as f:
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
    "MemoryLayerConfig": "MemoryLayerConfig" in classes,
    "QualityGateConfig": "QualityGateConfig" in classes,
    "PromotionScoreWeights": "PromotionScoreWeights" in classes,
    "ICMEConfig": "ICMEConfig" in classes,
    "StoragePathConfig": "StoragePathConfig" in classes,
    "ConfigManager": "ConfigManager" in classes,
    "DEFAULT_CONFIG": "DEFAULT_CONFIG = ICMEConfig()" in source,
    "StoragePathConfig.ensure()": "def ensure(self)" in source,
    "StoragePathConfig.validate()": "def validate(self)" in source,
    "StoragePathConfig.audit()": "def audit(self)" in source,
    "ConfigManager.health()": "def health(self)" in source and "ConfigManager" in classes,
    "ConfigManager.get_stats()": "def get_stats(self)" in source,
    "ConfigManager.ensure_storage()": "def ensure_storage(self)" in source,
    "ConfigManager.validate_storage()": "def validate_storage(self)" in source,
    "ConfigManager.audit_storage()": "def audit_storage(self)" in source,
    "ConfigManager.update_config()": "def update_config(self" in source,
    "ConfigManager.tick()": "def tick(self)" in source,
    "D9-1 道谱溯源": "D9-1" in source,
    "v9.1 docstring": "v9.1" in source and "配置管理 v9.1" in source,
    "EvolutionLoop灵活导入": "try:\n    from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "_recorder = recorder" in source,
    "learning_engine双注入": "_learning_engine = learning_engine" in source,
    "record_action(ensure_storage)": '"ensure_storage"' in source and 'record_action' in source,
    "record_action(validate_storage)": '"validate_storage"' in source,
    "record_action(audit_storage)": '"audit_storage"' in source,
    "record_action(update_config)": '"update_config"' in source,
    "3回调(_calc/_learn/_evolve)": all(f in funcs for f in ["health", "get_stats", "tick"]),
    "StoragePathConfig 15子路径": "causal_pairs" in source and "exports" in source and "tmp" in source,
}

print("\n=== M28 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)
