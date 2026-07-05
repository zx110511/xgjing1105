import json
import os
import re
import sqlite3

db_path = (
    r"c:\Users\Administrator\AppData\Roaming\Trae CN\User\globalStorage\state.vscdb"
)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get ALL keys and scan for agent-related data
cursor.execute("SELECT key, value FROM ItemTable")
all_rows = cursor.fetchall()

print(f"Total keys in state.vscdb: {len(all_rows)}")

# Find ALL agent unique_names
all_unique_names = set()
all_agent_names = set()
agent_data_list = []

for key, value in all_rows:
    if not isinstance(value, str):
        continue

    # Find all unique_name patterns
    matches = re.findall(r'"unique_name"\s*:\s*"([^"]+)"', value)
    for m in matches:
        all_unique_names.add(m)

    # Find all name patterns (in basic_info or top-level)
    name_matches = re.findall(r'"name"\s*:\s*"([^"]+)"', value)
    for m in name_matches:
        # Filter out non-agent names
        if (
            m not in ["Agent", "Chat", "custom", "dev_agent", "builtin", ""]
            and len(m) < 20
        ):
            all_agent_names.add(m)

    # Try to parse as JSON and find agent objects
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            if "unique_name" in parsed and "agent_id" in parsed:
                agent_data_list.append(
                    {
                        "from_key": key,
                        "name": parsed.get("name"),
                        "unique_name": parsed.get("unique_name"),
                        "type": parsed.get("type"),
                        "agent_id": parsed.get("agent_id"),
                    }
                )
            # Check nested
            for k, v in parsed.items():
                if isinstance(v, dict) and "unique_name" in v and "name" in v:
                    agent_data_list.append(
                        {
                            "from_key": f"{key}.{k}",
                            "name": v.get("name"),
                            "unique_name": v.get("unique_name"),
                            "type": v.get("type", "nested"),
                        }
                    )
    except:
        pass

print(f"\n=== All unique_names found ({len(all_unique_names)}) ===")
for name in sorted(all_unique_names):
    print(f"  {name}")

print(f"\n=== All agent names found ({len(all_agent_names)}) ===")
for name in sorted(all_agent_names):
    print(f"  {name}")

print(f"\n=== Agent data objects ({len(agent_data_list)}) ===")
for a in agent_data_list:
    print(
        f"  {a['name']} / {a['unique_name']} (type={a['type']}, from={a['from_key'][:50]})"
    )

# Also scan workspace agents directory
agents_dir = r"d:\元初系统\天机v9.1\.trae\agents"
agent_files = [
    f
    for f in os.listdir(agents_dir)
    if f.startswith("trae-official-") and f.endswith(".json")
]

print(f"\n=== Workspace agent config files ({len(agent_files)}) ===")
for f in sorted(agent_files):
    print(f"  {f}")

conn.close()
