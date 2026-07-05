import os, re, ast, sys

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

                # Extract module docstring
                docstring = ""
                try:
                    tree = ast.parse(content)
                    docstring = ast.get_docstring(tree) or ""
                except Exception:
                    pass
                docstring = docstring[:80].replace("\n", " ").replace("|", "/")

                # Extract imports from core
                core_imports = []
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("from core.") or line.startswith("from ."):
                        core_imports.append(line[:60])
                    elif line.startswith("from core import"):
                        core_imports.append(line[:60])
                imports_str = ";".join(core_imports[:5])

                results.append((rel, lines, classes, funcs, docstring, imports_str))
            except Exception as e:
                results.append((rel, "?", "?", "?", str(e)[:40], ""))

results.sort()
for rel, lines, classes, funcs, doc, imports in results:
    print(f"{rel}|{lines}|{classes}|{funcs}|{doc}|{imports}")
