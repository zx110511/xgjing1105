import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ast
import py_compile
from pathlib import Path

ct_path = Path(r"d:\元初系统\天机v9.1\core\chinese_tokenizer.py")

print("=== M27 ChineseTokenizer v1.1 语法编译 ===")
try:
    py_compile.compile(str(ct_path), doraise=True)
    print("✅ py_compile: PASS")
except py_compile.PyCompileError as e:
    print(f"❌ py_compile: FAIL — {e}")
    sys.exit(1)

with open(ct_path, "r", encoding="utf-8-sig") as f:
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
print(f"    Functions: {len(funcs)}")

checks = {
    "ChineseTokenizer类": "ChineseTokenizer" in classes,
    "tokenize_for_fts()": "tokenize_for_fts" in funcs,
    "tokenize_query()": "tokenize_query" in funcs,
    "tokenize_query_or()": "tokenize_query_or" in funcs,
    "add_hot_word()": "add_hot_word" in funcs,
    "health()": "health" in funcs,
    "get_stats()": "get_stats" in funcs,
    "tick()": "tick" in funcs,
    "_calc_tokenizer_effectiveness()": "_calc_tokenizer_effectiveness" in funcs,
    "_learn_from_tokenizer()": "_learn_from_tokenizer" in funcs,
    "_evolve_tokenizer_config()": "_evolve_tokenizer_config" in funcs,
    "is_cjk()": "is_cjk" in funcs,
    "get_tokenizer_status()": "get_tokenizer_status" in funcs,
    "D8-4 道谱溯源": "D8-4" in source,
    "v1.1 docstring": "v1.1" in source,
    "EvolutionLoop灵活导入": "from .evolution_loop import EvolutionLoop" in source,
    "recorder双注入": "self._recorder = recorder" in source,
    "learning_engine双注入": "self._learning_engine = learning_engine" in source,
    "record_action(tokenize_for_fts)": 'action="tokenize_for_fts"' in source,
    "record_action(tokenize_query)": 'action="tokenize_query"' in source,
    "record_action(tokenize_query_or)": 'action="tokenize_query_or"' in source,
    "record_action(add_hot_word)": 'action="add_hot_word"' in source,
    "stats(tokenize_calls)": '"tokenize_calls"' in source,
    "stats(query_calls)": '"query_calls"' in source,
    "stats(hot_word_adds)": '"hot_word_adds"' in source,
    "stats(bigram_fallbacks)": '"bigram_fallbacks"' in source,
    "module tokenize_for_fts": "def tokenize_for_fts" in source,
    "module tokenize_query": "def tokenize_query" in source,
    "module add_hot_word": "def add_hot_word" in source,
}

print("\n=== M27 审计检查 ===")
all_pass = True
for name, result in checks.items():
    status = "✅" if result else "❌"
    if not result:
        all_pass = False
    print(f"  {status} {name}")

print(f"\n{'🎉 ALL {}/{} PASS' if all_pass else '❌ FAILURES DETECTED'}".format(
    sum(1 for v in checks.values() if v), len(checks)))
sys.exit(0 if all_pass else 1)
