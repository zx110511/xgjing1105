import json
import os

# Check Preferences file
pref_path = r"c:\Users\Administrator\AppData\Roaming\Trae CN\Preferences"
try:
    with open(pref_path, encoding="utf-8-sig") as f:
        prefs = json.load(f)

    # Search for agent-related keys
    def find_agents(obj, path=""):
        results = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = k.lower()
                if "agent" in kl or "custom" in kl:
                    if isinstance(v, (dict, list)):
                        results.append((f"{path}.{k}", type(v).__name__, str(v)[:200]))
                    else:
                        results.append((f"{path}.{k}", type(v).__name__, str(v)[:100]))
                results.extend(find_agents(v, f"{path}.{k}"))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                results.extend(find_agents(item, f"{path}[{i}]"))
        return results

    agent_prefs = find_agents(prefs)
    print(f"=== Agent-related preferences ({len(agent_prefs)}) ===")
    for path, typ, val in agent_prefs[:30]:
        print(f"  {path} ({typ}): {val}")
except Exception as e:
    print(f"Error reading Preferences: {e}")

# Check IndexedDB
indexed_db_path = r"c:\Users\Administrator\AppData\Roaming\Trae CN\Default\IndexedDB"
if os.path.exists(indexed_db_path):
    print("\n=== IndexedDB directory exists ===")
    for root, dirs, files in os.walk(indexed_db_path):
        for f in files:
            if f.endswith(".db") or f.endswith(".ldb"):
                print(f"  {os.path.join(root, f)[:200]}")
else:
    print(f"\n=== IndexedDB directory not found at {indexed_db_path} ===")

# Check Local Storage
local_storage_path = (
    r"c:\Users\Administrator\AppData\Roaming\Trae CN\Default\Local Storage"
)
if os.path.exists(local_storage_path):
    print("\n=== Local Storage directory exists ===")
    for f in os.listdir(local_storage_path)[:20]:
        print(f"  {f}")
else:
    # Try other paths
    for candidate in [
        r"c:\Users\Administrator\AppData\Roaming\Trae CN\User\Local Storage",
        r"c:\Users\Administrator\AppData\Local\Trae CN\User Data\Default\Local Storage",
    ]:
        if os.path.exists(candidate):
            print(f"\n=== Local Storage found at {candidate} ===")
            break
    else:
        print("\n=== Local Storage not found in common locations ===")

# List all directories in Trae CN
print("\n=== All Trae CN directories ===")
base = r"c:\Users\Administrator\AppData\Roaming\Trae CN"
for item in sorted(os.listdir(base)):
    item_path = os.path.join(base, item)
    if os.path.isdir(item_path):
        print(f"  [DIR] {item}")
    else:
        print(f"  [FILE] {item}")
