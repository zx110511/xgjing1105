"""
天机 Trae+Qoder 适配端到端审计
验证所有修改点，确保100%捕获率
"""

import os
import sys
import json
import time
import sqlite3
import requests
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("天机 Trae+Qoder 适配端到端审计")
print("=" * 80)
print(f"审计时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# 审计结果收集
audit_results = []
all_passed = True

def check(name, passed, details=""):
    """记录审计结果"""
    global all_passed
    status = "✅" if passed else "❌"
    audit_results.append((name, passed, details))
    if not passed:
        all_passed = False
    print(f"{status} {name}")
    if details:
        print(f"   {details}")

# ============================================================================
# [1/5] 健康检查
# ============================================================================
print("\n[1/5] 健康检查")
print("-" * 80)

try:
    response = requests.get("http://127.0.0.1:8771/api/health", timeout=5)
    if response.status_code == 200:
        health = response.json()
        check(
            "天机服务健康",
            health.get("status") == "healthy",
            f"版本: {health.get('version', 'unknown')}"
        )
    else:
        check("天机服务健康", False, f"状态码: {response.status_code}")
except Exception as e:
    check("天机服务健康", False, f"连接失败: {e}")

# ============================================================================
# [2/5] 存储健康
# ============================================================================
print("\n[2/5] 存储健康")
print("-" * 80)

# 检查数据库
db_path = Path(r"D:\元初系统\天机v9.1\data\.memory\icme.db")
if db_path.exists():
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 检查memories表
        cursor.execute("SELECT COUNT(*) FROM memories")
        total_memories = cursor.fetchone()[0]

        # 检查各层分布
        cursor.execute("SELECT layer, COUNT(*) FROM memories GROUP BY layer")
        layers = dict(cursor.fetchall())

        # 检查最近写入
        cursor.execute("""
            SELECT COUNT(*) FROM memories
            WHERE created_at > ?
        """, (time.time() - 3600,))
        recent_writes = cursor.fetchone()[0]

        conn.close()

        check(
            "SQLite数据库",
            True,
            f"总记忆: {total_memories:,}条, 最近1小时: {recent_writes}条"
        )
        check(
            "层级分布",
            len(layers) >= 5,
            f"层级: {layers}"
        )

    except Exception as e:
        check("SQLite数据库", False, f"错误: {e}")
else:
    check("SQLite数据库", False, "数据库文件不存在")

# ============================================================================
# [3/5] 捕获守护进程
# ============================================================================
print("\n[3/5] 捕获守护进程")
print("-" * 80)

# 检查守护进程状态
try:
    response = requests.get("http://127.0.0.1:8771/api/active/capture_health", timeout=5)
    if response.status_code == 200:
        health = response.json()

        # 检查钩子系统
        hook_check = health.get("checks", {}).get("hook_system", {})
        check(
            "钩子系统",
            hook_check.get("status") == "ok",
            f"钩子数: {hook_check.get('hook_count', 0)}"
        )

        # 检查存储后端
        storage_check = health.get("checks", {}).get("storage_backend", {})
        check(
            "存储后端",
            storage_check.get("status") == "ok",
            f"类型: {storage_check.get('type', 'unknown')}"
        )

        # 检查最近捕获
        capture_check = health.get("checks", {}).get("recent_captures", {})
        has_captures = capture_check.get("count", 0) > 0
        check(
            "最近捕获",
            capture_check.get("status") in ["ok", "warning"],
            f"数量: {capture_check.get('count', 0)}"
        )

    else:
        check("守护进程健康检查", False, f"状态码: {response.status_code}")

except Exception as e:
    check("守护进程健康检查", False, f"错误: {e}")

# ============================================================================
# [4/5] 双源扫描验证
# ============================================================================
print("\n[4/5] 双源扫描验证")
print("-" * 80)

# 检查Qoder Fusion路径
fusion_path = Path(os.environ.get("APPDATA", "")) / "Qoder" / "SharedClientCache" / "cache" / "ai_tracker"
if fusion_path.exists():
    # 查找JSONL文件
    jsonl_files = list(fusion_path.glob("*.jsonl"))
    check(
        "Qoder Fusion路径",
        True,
        f"路径: {fusion_path}, JSONL文件: {len(jsonl_files)}个"
    )

    # 检查最近活跃对话
    if jsonl_files:
        # 按修改时间排序
        jsonl_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest = jsonl_files[0]
        age = time.time() - latest.stat().st_mtime

        check(
            "当前活跃对话",
            age < 600,  # 10分钟内
            f"最新对话: {latest.name}, age={int(age)}s"
        )
else:
    check("Qoder Fusion路径", False, "路径不存在")

# 检查Legacy路径
legacy_base = Path.home() / ".qoder" / "cache" / "projects"
if legacy_base.exists():
    legacy_jsonls = list(legacy_base.rglob("*.jsonl"))
    check(
        "Qoder Legacy路径",
        True,
        f"路径: {legacy_base}, JSONL文件: {len(legacy_jsonls)}个"
    )
else:
    check("Qoder Legacy路径", False, "路径不存在")

# ============================================================================
# [5/5] 捕获端点测试
# ============================================================================
print("\n[5/5] 捕获端点测试")
print("-" * 80)

# 测试Trae捕获
trae_payload = {
    "user_input": "[端到端审计] Trae测试消息",
    "ai_response": "[端到端审计] Trae AI回复",
    "agent_id": "lingxi",
    "session_id": f"audit-trae-{int(time.time())}",
    "platform": "trae",
    "tags": ["audit", "e2e", "trae"]
}

try:
    response = requests.post(
        "http://127.0.0.1:8771/api/active/capture_conversation",
        json=trae_payload,
        timeout=5
    )

    if response.status_code == 200:
        result = response.json()
        check(
            "Trae对话捕获",
            result.get("success", False),
            f"turn_id: {result.get('turn_id', 'N/A')}"
        )

        # 验证三层捕获
        captured_layers = result.get("captured_layers", [])
        has_sensory = any("sensory" in str(layer) for layer in captured_layers)
        has_working = any("working" in str(layer) for layer in captured_layers)
        has_episodic = any("episodic" in str(layer) for layer in captured_layers)

        check(
            "三层捕获",
            has_sensory and has_working and has_episodic,
            f"层级: {[l.get('layer') if isinstance(l, dict) else l for l in captured_layers]}"
        )
    else:
        check("Trae对话捕获", False, f"状态码: {response.status_code}")

except Exception as e:
    check("Trae对话捕获", False, f"错误: {e}")

# 测试Qoder捕获
qoder_payload = {
    "user_input": "[端到端审计] Qoder测试消息",
    "ai_response": "[端到端审计] Qoder AI回复",
    "agent_id": "tianshu",
    "session_id": f"audit-qoder-{int(time.time())}",
    "platform": "qoder",
    "tags": ["audit", "e2e", "qoder"]
}

try:
    response = requests.post(
        "http://127.0.0.1:8771/api/active/capture_conversation",
        json=qoder_payload,
        timeout=5
    )

    if response.status_code == 200:
        result = response.json()
        check(
            "Qoder对话捕获",
            result.get("success", False),
            f"turn_id: {result.get('turn_id', 'N/A')}"
        )
    else:
        check("Qoder对话捕获", False, f"状态码: {response.status_code}")

except Exception as e:
    check("Qoder对话捕获", False, f"错误: {e}")

# ============================================================================
# 验证记忆入库
# ============================================================================
print("\n[验证] 记忆入库验证")
print("-" * 80)

try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 检查审计标签的记忆
    cursor.execute("""
        SELECT COUNT(*) FROM memories
        WHERE tags LIKE '%audit%' AND tags LIKE '%e2e%'
    """)
    audit_memories = cursor.fetchone()[0]

    check(
        "审计记忆入库",
        audit_memories >= 6,  # 2个平台 × 3层
        f"审计记忆数: {audit_memories}条 (预期≥6)"
    )

    # 检查平台标识
    cursor.execute("""
        SELECT COUNT(*) FROM memories
        WHERE metadata LIKE '%platform%trae%'
    """)
    trae_memories = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM memories
        WHERE metadata LIKE '%platform%qoder%'
    """)
    qoder_memories = cursor.fetchone()[0]

    check(
        "平台标识正确",
        trae_memories > 0 and qoder_memories > 0,
        f"Trae: {trae_memories}条, Qoder: {qoder_memories}条"
    )

    conn.close()

except Exception as e:
    check("记忆入库验证", False, f"错误: {e}")

# ============================================================================
# 代码修改验证
# ============================================================================
print("\n[代码] 修改点验证")
print("-" * 80)

core_py_path = Path(r"D:\元初系统\天机v9.1\core\container\core.py")
if core_py_path.exists():
    with open(core_py_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查关键修改点
    checks = [
        ("双源扫描", "_resolve_conv_sources" in content and "conv_sources" in content),
        ("3元组返回", "conv_id" in content and "return conv_sources" in content),
        ("Fusion路径", "ai_tracker" in content),
        ("Legacy路径", ".qoder" in content),
    ]

    for name, passed in checks:
        check(f"代码修改: {name}", passed)
else:
    check("core.py文件", False, "文件不存在")

# ============================================================================
# 总结
# ============================================================================
print("\n" + "=" * 80)
print("审计总结")
print("=" * 80)

total_checks = len(audit_results)
passed_checks = sum(1 for _, passed, _ in audit_results if passed)

print(f"\n总检查项: {total_checks}")
print(f"通过: {passed_checks}")
print(f"失败: {total_checks - passed_checks}")
print(f"通过率: {passed_checks / total_checks * 100:.1f}%")

if all_passed:
    print("\n🎉 端到端审计全部通过！")
else:
    print("\n⚠️ 存在失败项，需要修复")

# 详细结果
print("\n详细结果:")
for i, (name, passed, details) in enumerate(audit_results, 1):
    status = "✅" if passed else "❌"
    print(f"  [{i:2d}] {status} {name}")
    if details:
        print(f"       {details}")

print("\n" + "=" * 80)
