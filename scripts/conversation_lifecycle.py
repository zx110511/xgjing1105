# -*- coding: utf-8-sig -*-
"""conversation_lifecycle.py — 对话生命周期必做清单验证脚本

验证Agent是否在对话开始/结束时执行了必做清单。
由Agent主动运行以自检合规性，亦可被审计系统调用。

用法:
    python scripts/conversation_lifecycle.py check_start <session_id>
    python scripts/conversation_lifecycle.py check_end <session_id>
    python scripts/conversation_lifecycle.py audit <session_id>

退出码:
    0: 合规通过
    1: 有缺失项但已补归档
    2: 严重违规
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

TIANJI_API_URL = "http://127.0.0.1:8771"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OFFLINE_QUEUE = PROJECT_ROOT / ".tianji" / "offline_writes.json"


def _api_get(
    path: str, params: dict | None = None, timeout: int = 5
) -> dict | list | None:
    url = f"{TIANJI_API_URL}{path}"
    if params:
        from urllib.parse import urlencode

        url = f"{url}?{urlencode(params)}"
    try:
        req = urllib.request.Request(url)
        r = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return {"error": str(e)}


def _api_post(path: str, data: dict, timeout: int = 30) -> dict | None:
    try:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{TIANJI_API_URL}{path}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        r = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return {"error": str(e)}


def check_start(session_id: str) -> int:
    """对话开始必做清单验证"""
    print(f"[对话开始检查] session={session_id}")
    issues = []

    # Step 1: 系统健康
    health = _api_get("/api/health")
    if not health or (isinstance(health, dict) and health.get("error")):
        issues.append("Step1: 天机8771服务不可用")
        print("  [X] Step1: 天机服务不可用")
    else:
        status = (
            health.get("status", "unknown") if isinstance(health, dict) else "unknown"
        )
        print(f"  [V] Step1: 天机服务={status}")

    # Step 2: 检查最近5分钟内是否有该session的memory_recall记录
    # (通过检索L1 Working层是否有该session的活跃记录间接验证)
    recent = _api_get("/api/platform/recall", {"query": session_id, "limit": 5})
    if recent and isinstance(recent, list) and len(recent) > 0:
        print(f"  [V] Step2: 找到{len(recent)}条相关记忆")
    else:
        print("  [!] Step2: 未找到session相关记忆(可能为新会话)")

    # Step 3-5: 复杂度判断/调度/规则验证
    # (这些步骤由Agent在对话过程中执行，此处只检查是否有TVP声明记录)
    print("  [i] Step3-5: 复杂度判断/调度/规则验证由Agent在对话中执行")

    if issues:
        print(f"\n[结果] 有 {len(issues)} 个问题: {issues}")
        return 1
    print("\n[结果] 对话开始检查通过")
    return 0


def check_end(session_id: str) -> int:
    """对话结束必做清单验证"""
    print(f"[对话结束检查] session={session_id}")
    issues = []

    # Step 1: 对话内容归档 (L3 episodic)
    recall_episodic = _api_post(
        "/api/search/",
        {"query": session_id, "limit": 10, "layer": "episodic"},
    )
    if isinstance(recall_episodic, dict) and recall_episodic.get("results"):
        archive_found = any(
            "conversation-archive" in (r.get("tags") or [])
            for r in recall_episodic["results"]
        )
        if archive_found:
            print("  [V] Step1: 找到对话归档(L3 Episodic)")
        else:
            issues.append("Step1: 未找到conversation-archive标签的归档")
            print("  [X] Step1: 未找到对话归档")
    else:
        issues.append("Step1: L3 Episodic层无该session记录")
        print("  [X] Step1: L3 Episodic层无该session记录")

    # Step 2: 文件变更同步 (L4 semantic, tag=file-sync)
    recall_semantic = _api_post(
        "/api/search/",
        {"query": "file-sync", "limit": 10, "layer": "semantic"},
    )
    if isinstance(recall_semantic, dict) and recall_semantic.get("results"):
        print(f"  [V] Step2: 找到{len(recall_semantic['results'])}条文件同步记录")

    # Step 3: 系统决策 (L5 meta, tag=system-decision)
    recall_meta = _api_post(
        "/api/search/",
        {"query": "system-decision", "limit": 5, "layer": "meta"},
    )
    if isinstance(recall_meta, dict) and recall_meta.get("results"):
        print(f"  [V] Step3: 找到{len(recall_meta['results'])}条系统决策记录")

    if issues:
        print(f"\n[结果] 有 {len(issues)} 个问题，建议补归档")
        return 1
    print("\n[结果] 对话结束检查通过")
    return 0


def auto_archive(session_id: str, content: str, layer: str = "episodic") -> bool:
    """自动归档到指定层"""
    data = {
        "content": content,
        "layer": layer,
        "tags": ["conversation-archive", "auto-capture", f"session:{session_id}"],
        "priority": "high",
        "use_llm": False,
    }
    result = _api_post("/api/memory/", data, timeout=30)
    if result and not (isinstance(result, dict) and result.get("error")):
        print(f"  [V] 归档成功: layer={layer} id={result.get('id')}")
        return True
    # 失败时写入离线队列
    offline_path = OFFLINE_QUEUE
    offline_path.parent.mkdir(parents=True, exist_ok=True)
    queue = []
    if offline_path.exists():
        try:
            queue = json.loads(offline_path.read_text(encoding="utf-8"))
        except Exception:
            queue = []
    queue.append(
        {
            "id": f"offline-{len(queue) + 1:03d}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "layer": layer,
            "priority": "high",
            "tags": data["tags"],
            "content": content,
        }
    )
    offline_path.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [!] 归档失败，已写入离线队列: {offline_path}")
    return False


def audit(session_id: str) -> int:
    """完整审计：开始+结束+缺失项补归档"""
    print(f"\n{'=' * 60}")
    print(f"[对话生命周期审计] session={session_id}")
    print(f"{'=' * 60}")
    start_rc = check_start(session_id)
    print()
    end_rc = check_end(session_id)
    print()
    if end_rc != 0:
        print("[补归档] 检测到缺失项，尝试自动归档...")
        auto_archive(
            session_id,
            content=f"对话生命周期审计补归档: session={session_id} timestamp={time.strftime('%Y-%m-%dT%H:%M:%S')}",
            layer="episodic",
        )
    print(f"\n{'=' * 60}")
    print(f"[审计完成] start_rc={start_rc} end_rc={end_rc}")
    print(f"{'=' * 60}")
    return 0 if start_rc == 0 and end_rc == 0 else 1


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    action = sys.argv[1]
    session_id = sys.argv[2]
    if action == "check_start":
        return check_start(session_id)
    elif action == "check_end":
        return check_end(session_id)
    elif action == "audit":
        return audit(session_id)
    elif action == "auto_archive":
        content = sys.argv[3] if len(sys.argv) > 3 else f"manual archive {session_id}"
        layer = sys.argv[4] if len(sys.argv) > 4 else "episodic"
        return 0 if auto_archive(session_id, content, layer) else 1
    else:
        print(f"未知动作: {action}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
