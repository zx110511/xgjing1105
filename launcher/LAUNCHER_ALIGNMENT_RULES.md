# 天机v9.1 启动文件最强修复对齐规则 (Launcher Alignment Rules)

**版本**: v1.0 | **生效**: 2026-06-25 | **优先级**: P0-强制

---

## 一、修复对齐检查清单 (强制执行)

### 1. 配置文件检查

| 检查项 | 文件路径 | 检查内容 | 正确标准 | 修复动作 |
|--------|---------|---------|---------|---------|
| ✅ 项目根目录 | config/tianji.conf | project_root字段 | D:\元初系统\天机v9.1 | 修正路径 |
| ✅ 端口配置 | config/tianji.conf | ports.tianji.main | 8771 | 修正端口 |
| ✅ 启动命令 | .trae/config/launcher.json | launch_sequence.command | D:\元初系统\天机v9.1\python\python.exe -m launcher.tianji_v91_launcher | 修正命令 |
| ✅ 健康端点 | .trae/config/launcher.json | health_endpoints.primary | http://127.0.0.1:8771/api/health | 修正端点 |
| ✅ PowerShell端口 | scripts/tools/start-tianji.ps1 | $Port变量 | 8771 | 修正端口 |
| ✅ 启动文件存在 | launcher/tianji_v91_launcher.py | 文件存在 | 存在且可执行 | 创建/修复 |
| ⚠️ 环境变量密钥 | .env | DEEPSEEK_API_KEY | 使用环境变量引用 | 移除硬编码 |

### 2. 启动文件完整性检查

| 检查项 | 检查内容 | 正确标准 | 修复动作 |
|--------|---------|---------|---------|
| ✅ UTF-8编码 | 文件编码 | UTF-8-SIG | 修正编码 |
| ✅ 端口强制 | PORT常量 | 8771 | 修正端口 |
| ✅ Python路径 | sys.executable | 动态获取 | 禁止硬编码 |
| ✅ 健康检查 | /api/health端点 | 存在且响应healthy | 修复端点 |
| ✅ PID文件管理 | .daemon/tianji.pid | 正确写入/清理 | 修复PID逻辑 |
| ✅ 日志目录 | logs/目录 | 存在且可写 | 创建目录 |

---

## 二、修复对齐执行流程 (强制执行)

### Step 1: 扫描检查
```powershell
# 执行修复对齐扫描
python d:\元初系统\天机v9.1\scripts\sss_audit.py
```

### Step 2: 配置验证
```powershell
# 验证配置文件
python -c "import json; c=json.load(open('config/tianji.conf')); print('project_root:', c['system']['project_root']); print('port:', c['ports']['tianji']['main'])"
```

### Step 3: 端口检查
```powershell
# 检查端口8771是否可用
Get-NetTCPConnection -LocalPort 8771 -State Listen -ErrorAction SilentlyContinue
```

### Step 4: 启动验证
```powershell
# 启动天机服务
python d:\元初系统\天机v9.1\launcher\tianji_v91_launcher.py --daemon
```

### Step 5: 健康检查
```powershell
# 验证健康端点
Invoke-RestMethod -Uri http://127.0.0.1:8771/api/health -Method Get
```

### Step 6: 修复确认
```powershell
# 确认所有检查项通过
python d:\元初系统\天机v9.1\scripts\sss_audit.py
```

---

## 三、禁止事项 (P0强制)

- ❌ 禁止使用端口8778 (违反宪法)
- ❌ 禁止硬编码API密钥 (违反宪法第1条)
- ❌ 禁止引用不存在的launcher/tianji_launcher.py
- ❌ 禁止使用v8.1路径配置
- ❌ 禁止跳过健康检查
- ❌ 禁止忽略PID文件管理

---

## 四、必须事项 (P0强制)

- ✅ 必须使用UTF-8-SIG编码
- ✅ 必须使用端口8771
- ✅ 必须使用v9.1路径配置
- ✅ 必须通过launcher.tianji_v91_launcher启动
- ✅ 必须执行健康检查
- ✅ 必须管理PID文件
- ✅ 必须使用环境变量引用密钥

---

## 五、修复对齐自动化脚本 (推荐)

```python
# launcher_alignment_check.py
import json
import os
from pathlib import Path

def check_launcher_alignment():
    """启动文件修复对齐检查"""
    root = Path("D:/元初系统/天机v9.1")
    
    checks = {
        "config_tianji_root": False,
        "config_tianji_port": False,
        "launcher_json_command": False,
        "start_ps1_port": False,
        "launcher_file_exists": False,
        "env_no_hardcoded_key": False
    }
    
    # Check 1: config/tianji.conf
    try:
        conf = json.load(open(root / "config" / "tianji.conf"))
        if conf["system"]["project_root"] == "D:\\元初系统\\天机v9.1":
            checks["config_tianji_root"] = True
        if conf["ports"]["tianji"]["main"] == 8771:
            checks["config_tianji_port"] = True
    except:
        pass
    
    # Check 2: .trae/config/launcher.json
    try:
        launcher_json = json.load(open(root / ".trae" / "config" / "launcher.json"))
        cmd = launcher_json["launch_sequence"][0]["command"]
        if "launcher.tianji_v91_launcher" in cmd:
            checks["launcher_json_command"] = True
    except:
        pass
    
    # Check 3: scripts/tools/start-tianji.ps1
    try:
        ps1_content = (root / "scripts" / "tools" / "start-tianji.ps1").read_text()
        if "$Port = 8771" in ps1_content:
            checks["start_ps1_port"] = True
    except:
        pass
    
    # Check 4: launcher/tianji_v91_launcher.py
    if (root / "launcher" / "tianji_v91_launcher.py").exists():
        checks["launcher_file_exists"] = True
    
    # Check 5: .env
    try:
        env_content = (root / ".env").read_text()
        if "DEEPSEEK_API_KEY=sk-" not in env_content:
            checks["env_no_hardcoded_key"] = True
    except:
        pass
    
    # Report
    print("=" * 60)
    print("启动文件修复对齐检查报告")
    print("=" * 60)
    for check, status in checks.items():
        symbol = "✅" if status else "❌"
        print(f"{symbol} {check}: {status}")
    print("=" * 60)
    
    all_passed = all(checks.values())
    if all_passed:
        print("✅ 所有检查项通过")
    else:
        print("❌ 存在未通过检查项，需要修复")
    
    return all_passed

if __name__ == "__main__":
    check_launcher_alignment()
```

---

## 六、修复对齐记录机制 (强制)

每次修复对齐执行必须记录：
- 修复时间 (ISO8601格式)
- 修复项列表 (检查项+修复动作)
- 修复结果 (成功/失败)
- 记录到L3 Episodic (事件经历) + L5 Meta (系统策略)

---

**版本**: 1.0.0 | **生效**: 2026-06-25 | **维护**: @tianshu + @tiewei
**核心目标**: 确保启动文件100%符合宪法规范，零硬编码，零配置错误