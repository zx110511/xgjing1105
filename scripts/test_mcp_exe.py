import subprocess
import json
import time
import sys

servers = [
    ("天机-调度", "D:\\元初系统\\天机v9.1\\dist\\天机-调度\\天机-调度.exe", {"PROJECT_ROOT": "D:\\元初系统\\天机v9.1"}),
    ("天机-执行器", "D:\\元初系统\\天机v9.1\\dist\\天机-执行器\\天机-执行器.exe", {"PROJECT_ROOT": "D:\\元初系统\\天机v9.1"}),
    ("天机-运维", "D:\\元初系统\\天机v9.1\\dist\\天机-运维\\天机-运维.exe", {"PROJECT_ROOT": "D:\\元初系统\\天机v9.1"}),
    ("天机-洞察", "D:\\元初系统\\天机v9.1\\dist\\天机-洞察\\天机-洞察.exe", {"PROJECT_ROOT": "D:\\元初系统\\天机v9.1"}),
    ("天机-铁卫", "D:\\元初系统\\天机v9.1\\dist\\天机-铁卫\\天机-铁卫.exe", {"PROJECT_ROOT": "D:\\元初系统\\天机v9.1"}),
    ("天机-忆库", "D:\\元初系统\\天机v9.1\\dist\\天机-忆库\\天机-忆库.exe", {"AI_MEMORY_ROOT": "D:\\元初系统\\天机v9.1", "TIANJI_API_URL": "http://127.0.0.1:8771"}),
]

init_msg = json.dumps({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}
}) + "\n"

tools_msg = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n"

results = []
for name, exe_path, env in servers:
    try:
        full_env = dict(__import__("os").environ)
        full_env.update(env)
        proc = subprocess.Popen(
            [exe_path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=full_env, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        proc.stdin.write(init_msg.encode("utf-8"))
        proc.stdin.flush()
        time.sleep(1.5)
        proc.stdin.write(tools_msg.encode("utf-8"))
        proc.stdin.flush()
        time.sleep(1.5)
        proc.stdin.close()
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()

        init_ok = False
        tools_count = 0
        tool_names = []
        for line in stdout.decode("utf-8-sig", errors="replace").strip().split("\n"):
            if not line.strip():
                continue
            try:
                resp = json.loads(line)
                if resp.get("id") == 1 and "result" in resp:
                    init_ok = True
                    si = resp["result"].get("serverInfo", {})
                    print(f"  [{name}] Initialize: server={si.get('name')}, version={si.get('version')}, tools={si.get('tool_count')}")
                elif resp.get("id") == 2 and "result" in resp:
                    tools = resp["result"].get("tools", [])
                    tools_count = len(tools)
                    tool_names = [t["name"] for t in tools]
                    print(f"  [{name}] Tools ({tools_count}): {', '.join(tool_names)}")
            except json.JSONDecodeError:
                pass

        status = "✅" if init_ok and tools_count > 0 else "❌"
        results.append((name, status, init_ok, tools_count, tool_names))
        print(f"  [{name}] {status} init={'OK' if init_ok else 'FAIL'} tools={tools_count}")
    except Exception as e:
        results.append((name, "❌", False, 0, []))
        print(f"  [{name}] ❌ ERROR: {e}")

print("\n" + "=" * 60)
print("MCP Server EXE 测试汇总")
print("=" * 60)
total_tools = 0
for name, status, init_ok, tc, tn in results:
    total_tools += tc
    print(f"  {status} {name}: init={'OK' if init_ok else 'FAIL'}, tools={tc} {tn}")
print(f"\n总计: {sum(1 for r in results if r[1]=='✅')}/{len(results)} 成功, {total_tools} 个工具")
