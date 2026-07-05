import os

# Check IndexedDB
indexed_db_path = r"c:\Users\Administrator\AppData\Roaming\Trae CN\IndexedDB"
print("=== IndexedDB contents ===")
for root, dirs, files in os.walk(indexed_db_path):
    level = root.replace(indexed_db_path, "").count(os.sep)
    indent = " " * 2 * level
    print(f"{indent}{os.path.basename(root)}/")
    subindent = " " * 2 * (level + 1)
    for file in files[:10]:
        print(f"{subindent}{file}")
    if len(files) > 10:
        print(f"{subindent}... and {len(files) - 10} more files")
    if level >= 2:
        break

# Check for .db files in IndexedDB
print("\n=== IndexedDB .db files ===")
db_files = []
for root, dirs, files in os.walk(indexed_db_path):
    for f in files:
        if f.endswith(".db") or f.endswith(".leveldb") or "leveldb" in f.lower():
            db_files.append(os.path.join(root, f))
for f in db_files[:20]:
    print(f"  {f}")

# Check Local Storage
local_storage_path = r"c:\Users\Administrator\AppData\Roaming\Trae CN\Local Storage"
print("\n=== Local Storage contents ===")
for f in sorted(os.listdir(local_storage_path))[:30]:
    print(f"  {f}")

# Check ModularData
modular_path = r"c:\Users\Administrator\AppData\Roaming\Trae CN\ModularData"
if os.path.exists(modular_path):
    print("\n=== ModularData contents ===")
    for root, dirs, files in os.walk(modular_path):
        level = root.replace(modular_path, "").count(os.sep)
        indent = " " * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = " " * 2 * (level + 1)
        for file in files[:10]:
            print(f"{subindent}{file}")
        if level >= 3:
            break

# Try to find any file containing "custom_agent" or agent list
print("\n=== Searching for agent list files ===")
search_paths = [
    r"c:\Users\Administrator\AppData\Roaming\Trae CN\User",
    r"c:\Users\Administrator\AppData\Roaming\Trae CN\IndexedDB",
    r"c:\Users\Administrator\AppData\Roaming\Trae CN\Local Storage",
]

for sp in search_paths:
    if not os.path.exists(sp):
        continue
    for root, dirs, files in os.walk(sp):
        for f in files:
            fl = f.lower()
            if "agent" in fl or "custom" in fl:
                print(f"  {os.path.join(root, f)[:200]}")
