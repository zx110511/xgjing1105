import urllib.request, json

with open(r'D:\元初系统\天机v9.1\.trae\mcp.json', 'rb') as f:
    raw = f.read()
has_bom = raw[:3] == b'\xef\xbb\xbf'
data = json.loads(raw.decode('utf-8'))
servers = list(data.get('mcpServers', {}).keys())
print(f'1. .trae/mcp.json: BOM={has_bom}, Servers={servers}')

with open(r'c:\Users\Administrator\AppData\Roaming\Trae CN\User\mcp.json', 'r', encoding='utf-8') as f:
    udata = json.load(f)
disabled = [k for k, v in udata.get('mcpServers', {}).items() if v.get('disabled')]
print(f'2. User mcp.json: disabled={disabled}')

import subprocess, sys, time
init = json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'test','version':'1.0'}}}, ensure_ascii=False)
proc = subprocess.Popen([sys.executable, r'D:\元初系统\天机v9.1\mcp\tianji_mcp_server.py'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=r'D:\元初系统\天机v9.1')
proc.stdin.write((init + '\n').encode('utf-8'))
proc.stdin.flush()
time.sleep(2)
proc.terminate()
out, err = proc.communicate(timeout=5)
resp = json.loads(out.decode('utf-8').strip())
info = resp.get('result', {}).get('serverInfo', {})
name = info.get('name', '?')
ver = info.get('version', '?')
api_ok = info.get('api_available', False)
tools = info.get('tool_count', 0)
print(f'3. MCP Server: name={name}, version={ver}, api_available={api_ok}, tools={tools}')

r = urllib.request.urlopen('http://127.0.0.1:8771/api/health', timeout=5)
h = json.loads(r.read().decode('utf-8'))
print(f'4. API Health: status={h.get("status")}, engine={h.get("engine_ready")}')
