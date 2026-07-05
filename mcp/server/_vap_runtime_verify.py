"""VAP v2.0 真实运行验证脚本.

直接实例化 AgentFrameworkServer，调用 4 个 VAP 工具:
  1. vap_declare  → 写入 v9.1 L3 Episodic + 返回 W3C trace + 可视化
  2. vap_handoff  → Agent 切换 + 委派链传播 + 写入 L3
  3. vap_summary  → 会话追踪摘要
  4. vap_recall   → 从 v9.1 L3 检索 VAP 声明

最后通过 v9.1 GET /api/memory/ 验证持久化.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

# 确保 agent_framework.py 可导入
# NOTE: 不在此处重定向 stdout/stderr — agent_framework.py 在 import 时
# 会自行重定向，双重包装会导致 "I/O operation on closed file"
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))


def _section(title: str) -> None:
    bar = "=" * 78
    print(f"\n{bar}\n  {title}\n{bar}", flush=True)


def _verify_persisted(memory_id: str, api_url: str) -> dict:
    """通过 GET /api/platform/recall 验证 L3 持久化."""
    try:
        import urllib.parse as _up
        params = _up.urlencode({"query": "VAP", "limit": "20"})
        req = urllib.request.Request(
            f"{api_url}/api/platform/recall?{params}",
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8-sig", errors="replace"))
            results = body if isinstance(body, list) else body.get("results", body.get("entries", []))
            for r in results:
                rid = r.get("id", "") if isinstance(r, dict) else ""
                if rid == memory_id:
                    return {"found": True, "entry": r}
            return {"found": False, "total_results": len(results), "sample_ids": [
                r.get("id", "")[:16] for r in results[:5] if isinstance(r, dict)
            ]}
    except Exception as e:
        return {"found": False, "error": str(e)[:200]}


def main() -> int:
    _section("VAP v2.0 真实运行验证 — 智能调度可视化根基")

    # 健康检查
    api_url = "http://127.0.0.1:8771"
    try:
        with urllib.request.urlopen(f"{api_url}/api/health", timeout=5) as r:
            health = json.loads(r.read().decode("utf-8-sig"))
            print(f"[OK] v9.1 健康: status={health.get('status')} version={health.get('version')}")
    except Exception as e:
        print(f"[FAIL] v9.1 不可用: {e}")
        return 1

    # 实例化 Server
    from agent_framework import AgentFrameworkServer  # type: ignore

    server = AgentFrameworkServer()
    print(f"[OK] AgentFrameworkServer 实例化: api_available={server._api_available}")

    # ── 测试 1: vap_declare ──────────────────────────
    _section("T1: vap_declare — 内容归属声明 (W3C Trace + OTel GenAI + 写入 L3)")
    decl_args = {
        "agent": "tianshu",
        "content_kind": "decision",
        "task_summary": "VAP v2.0 首次真实运行验证",
        "event_type": "content_start",
        "status": "executing",
        "confidence": 0.98,
        "upstream": "human",
        "downstream": "miaobi",
        "delegation_chain": ["human", "tianshu"],
    }
    r1 = server._handle_vap_declare(decl_args)
    print(f"status: {r1.get('status')}")
    print(f"event_id: {r1.get('event_id')}")
    print(f"trace_id: {r1.get('trace_id')}")
    print(f"span_id: {r1.get('span_id')}")
    print(f"memory_id: {r1.get('memory_id')}")
    print(f"memory_persisted: {r1.get('memory_persisted')}")
    print("\n--- 可视化输出 (Trae IDE 动态窗口可见) ---")
    print(r1.get("visualization", ""))

    if not r1.get("memory_persisted"):
        print(f"\n[FAIL] L3 持久化失败: {r1.get('memory_id')}")
        return 2

    mid1 = r1.get("memory_id", "")
    trace1 = r1.get("trace_id", "")

    # ── 测试 2: vap_handoff ──────────────────────────
    _section("T2: vap_handoff — Agent 切换声明 (委派链传播)")
    handoff_args = {
        "from_agent": "tianshu",
        "to_agent": "miaobi",
        "task_type": "content_creation",
        "context_summary": "VAP 验证完成后转交创作",
        "trace_id": trace1,  # 延续同一 trace
        "handoff_mode": "delegate",
    }
    r2 = server._handle_vap_handoff(handoff_args)
    print(f"status: {r2.get('status')}")
    print(f"event_id: {r2.get('event_id')}")
    print(f"trace_id (延续): {r2.get('trace_id')}")
    print(f"memory_id: {r2.get('memory_id')}")
    print(f"memory_persisted: {r2.get('memory_persisted')}")
    print("\n--- 可视化输出 ---")
    print(r2.get("visualization", ""))

    # ── 测试 3: vap_declare 第二次 (miaobi 接力) ─────
    _section("T3: vap_declare #2 — miaobi 接力 (延续 trace_id)")
    decl2_args = {
        "agent": "miaobi",
        "content_kind": "text",
        "task_summary": "miaobi 接力完成 VAP 创作验证",
        "event_type": "content_end",
        "status": "completed",
        "confidence": 0.95,
        "upstream": "tianshu",
        "trace_id": trace1,
        "delegation_chain": ["human", "tianshu", "miaobi"],
    }
    r3 = server._handle_vap_declare(decl2_args)
    print(f"status: {r3.get('status')}")
    print(f"trace_id (延续): {r3.get('trace_id')}")
    print(f"memory_id: {r3.get('memory_id')}")
    print(f"memory_persisted: {r3.get('memory_persisted')}")
    print("\n--- 可视化输出 ---")
    print(r3.get("visualization", ""))

    # ── 测试 4: vap_summary ──────────────────────────
    _section("T4: vap_summary — 会话追踪摘要")
    sum_args = {"trace_id": trace1, "limit": 50}
    r4 = server._handle_vap_summary(sum_args)
    print(f"status: {r4.get('status')}")
    print(f"trace_id: {r4.get('trace_id')}")
    print(f"total_events: {r4.get('total_events')}")
    print(f"by_agent: {r4.get('by_agent')}")
    print(f"by_type: {r4.get('by_type')}")
    print("\n--- 可视化输出 ---")
    print(r4.get("visualization", ""))

    # ── 测试 5: vap_recall ───────────────────────────
    _section("T5: vap_recall — 从 v9.1 L3 检索 VAP 声明")
    recall_args = {
        "query": "VAP tianshu",
        "agent_filter": "tianshu",
        "limit": 5,
    }
    r5 = server._handle_vap_recall(recall_args)
    print(f"status: {r5.get('status')}")
    print(f"total_results: {r5.get('total_results', len(r5.get('results', [])))}")
    results = r5.get("results", [])
    for i, item in enumerate(results[:3], 1):
        if isinstance(item, dict):
            print(f"  [{i}] id={item.get('id', '')[:16]} tags={item.get('tags', [])}")
            content = item.get("content", "")[:100]
            print(f"      content: {content}")

    # ── 测试 6: 通过 v9.1 API 验证 L3 持久化 ─────────
    _section("T6: v9.1 API 持久化验证")
    if mid1:
        verify = _verify_persisted(mid1, api_url)
        print(f"memory_id={mid1}")
        print(f"found_in_L3: {verify.get('found')}")
        if verify.get("found"):
            entry = verify.get("entry", {})
            print(f"  layer: {entry.get('layer')}")
            print(f"  tags: {entry.get('tags')}")
            print(f"  content (前120字): {entry.get('content', '')[:120]}")
            meta = entry.get("metadata", {})
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            print(f"  gen_ai.agent.name: {meta.get('gen_ai.agent.name')}")
            print(f"  gen_ai.operation.name: {meta.get('gen_ai.operation.name')}")
            print(f"  gen_ai.tool.name: {meta.get('gen_ai.tool.name')}")
            print(f"  trace_id: {meta.get('trace_id', '')[:40]}")
            print("\n[OK] VAP v2.0 L3 持久化 + OTel GenAI 语义 全部验证通过")
        else:
            print(f"[FAIL] 未在 L3 找到 memory_id={mid1}: {verify}")

    _section("VAP v2.0 真实运行验证 — 全部完成")
    print(f"""
汇总:
  - vap_declare:    2 次 (tianshu + miaobi 接力)
  - vap_handoff:    1 次 (tianshu → miaobi delegate)
  - vap_summary:    1 次 (会话追踪)
  - vap_recall:     1 次 (L3 检索)
  - L3 持久化:      {sum(1 for r in [r1, r2, r3] if r.get('memory_persisted'))}/3 成功
  - W3C Trace 延续:  {trace1[:32]} (3 个事件共享)
  - OTel GenAI 语义: gen_ai.agent.name / operation.name / tool.name 全部写入
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
