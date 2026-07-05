import os, re

root = r"D:\元初系统\天机v9.1"
dirs = ["core", "server", "mcp", "agents", "indexing", "llm_integration", "active_memory", "adapters", "daemon", "config", "launcher"]

results = []
for d in dirs:
    full = os.path.join(root, d)
    if not os.path.exists(full):
        continue
    for dirpath, dirnames, filenames in os.walk(full):
        for fn in filenames:
            if not fn.endswith(".py") or fn == "__init__.py":
                continue
            fp = os.path.join(dirpath, fn)
            rel = fp.replace(root + "\\", "").replace("\\", "/")
            try:
                with open(fp, "r", encoding="utf-8-sig", errors="ignore") as f:
                    content = f.read()
                lines = content.count("\n") + 1
                classes = len(re.findall(r"^class \w+", content, re.MULTILINE))
                funcs = len(re.findall(r"^\s{0,4}def \w+", content, re.MULTILINE))
                results.append((rel, lines, classes, funcs))
            except Exception:
                results.append((rel, "?", "?", "?"))

results.sort()
total_lines = 0
total_classes = 0
total_funcs = 0
for rel, lines, classes, funcs in results:
    print(f"{rel}|{lines}|{classes}|{funcs}")
    if isinstance(lines, int):
        total_lines += lines
        total_classes += classes
        total_funcs += funcs

print(f"\nSUMMARY|{len(results)}|{total_lines}|{total_classes}|{total_funcs}")
