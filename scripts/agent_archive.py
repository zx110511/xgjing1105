# -*- coding: utf-8-sig -*-
"""
agent_archive.py — Agent对话归档工具 v2.1 (直连HTTP·独立脚本)
==============================================================

Agent对话结束时调用的独立Python脚本，完成4要素完整归档到天机ICME。

定位: Agent MCP直调不可用时的独立降级方案
  Agent正常运行: 直接调用MCP memory_remember (含TCL归一化+quality_gate) [推荐]
  本脚本: 直接HTTP POST到/api/memory/ (绕过MCP,独立可用) [降级/手动]

归档路径:
  直接HTTP POST → /api/memory/ (绕过MCP,无TCL处理)
  失败降级: 离线队列 → .tianji/offline_writes.json

用法:
  python scripts/agent_archive.py <input.json>
  python scripts/agent_archive.py -i <input.json>   (与上面相同)
  python scripts/agent_archive.py -s <session_id> -u "<用户消息>" -a "<Agent回复>" -d decisions.json -f files.json
  python scripts/agent_archive.py -c critical -s <session_id> ...   (指定复杂度)

输入JSON格式(input.json):
{
  "session_id": "session-001",          // 必填: 会话ID
  "user_message": "完整用户消息原文",     // 必填: 要素1
  "agent_response": "完整Agent回复原文",  // 必填: 要素2
  "agent_id": "tianji",                 // 可选: Agent ID, 默认tianji
  "complexity": "standard",             // 可选: trivial/standard/critical, 默认standard
  "decisions": [                        // 可选: 要素3-关键决策列表
    {"step": "Step1-识别", "agent": "tianji", "decision": "...", "reason": "...", "evidence": "..."}
  ],
  "file_changes": [                     // 可选: 要素4-文件变更列表
    {"path": "xxx.py", "type": "create", "lines": 280, "summary": "..."}
  ],
  "mcp_tools": ["tianji_health"],       // 可选: 使用的MCP工具
  "tvp_declarations": ["[TVP] ..."]      // 可选: TVP声明
}

输出: JSON
{
  "l3_id": "abc123",           // L3 Episodic记忆ID
  "l4_ids": ["def456", ...],   // L4 Semantic记忆ID列表
  "l5_id": "ghi789",           // L5 Meta记忆ID (仅critical级)
  "session_id": "session-001",
  "hash": "1a2b3c4d",
  "offline_queued": 0,
  "errors": []
}

归档策略:
  - L3 Episodic: 4要素合并为一条记录
  - L4 Semantic: 每个文件变更一条记录
  - L5 Meta: 仅critical级生成系统决策记录
  - 失败降级: 写入 .tianji/offline_writes.json

注意事项:
  - use_llm=false 避免LLM超时
  - UTF-8全链路安全
  - 无代理urllib(绕过HTTP_PROXY)
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

# UTF-8输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

API_URL = "http://127.0.0.1:8771"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OFFLINE_QUEUE = PROJECT_ROOT / ".tianji" / "offline_writes.json"
ERRORS: List[str] = []


def post_memory(content: str, layer: str, tags: List[str], priority: str,
                timeout: int = 30) -> Optional[str]:
    """HTTP POST到/api/memory/端点(绕过MCP TCL管道,独立可用)"""
    data = json.dumps(
        {"content": content, "layer": layer, "tags": tags,
         "priority": priority, "use_llm": False},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/api/memory/",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    r = opener.open(req, timeout=timeout)
    resp = json.loads(r.read().decode("utf-8"))
    return resp.get("id")


def safe_post_memory(content: str, layer: str, tags: List[str],
                     priority: str) -> Optional[str]:
    """直接HTTP POST(带离线队列降级)"""
    try:
        return post_memory(content, layer, tags, priority)
    except Exception as e:
        msg = f"{layer}层归档失败: {e}"
        ERRORS.append(msg)
        # 离线队列降级
        offline_item = {
            "id": f"offline-{int(time.time())}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "content": content[:500],
            "layer": layer,
            "tags": tags,
            "priority": priority,
        }
        try:
            OFFLINE_QUEUE.parent.mkdir(parents=True, exist_ok=True)
            queue = []
            if OFFLINE_QUEUE.exists():
                queue = json.loads(OFFLINE_QUEUE.read_text(encoding="utf-8"))
            queue.append(offline_item)
            OFFLINE_QUEUE.write_text(
                json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e2:
            ERRORS.append(f"离线队列写入失败: {e2}")
        return None


def archive(input_data: dict) -> dict:
    """执行4要素完整归档"""
    global ERRORS
    ERRORS = []

    session_id = input_data["session_id"]
    user_msg = input_data.get("user_message", "")
    agent_resp = input_data.get("agent_response", "")
    agent_id = input_data.get("agent_id", "tianji")
    complexity = input_data.get("complexity", "standard")
    decisions = input_data.get("decisions", [])
    file_changes = input_data.get("file_changes", [])
    mcp_tools = input_data.get("mcp_tools", [])
    tvp_decls = input_data.get("tvp_declarations", [])

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    content_hash = hashlib.sha256(
        f"{session_id}:1:{len(user_msg)}:{len(agent_resp)}".encode()
    ).hexdigest()[:16]

    result = {"l3_id": None, "l4_ids": [], "l5_id": None,
              "session_id": session_id, "hash": content_hash,
              "offline_queued": 0, "errors": []}

    # ── L3 Episodic: 4要素合并 ──
    # 要素3文本
    dec_text = "\n".join(
        f"- {d.get('step','?')} @{d.get('agent','?')}: {d.get('decision','?')}\n"
        f"  原因: {d.get('reason','-')}\n  证据: {d.get('evidence','-')}"
        for d in decisions
    ) if decisions else "(无关键决策)"

    # 要素4文本
    fc_text = "\n".join(
        f"- {fc.get('path','?')} [{fc.get('type','modify')}] +{fc.get('lines',0)}行\n"
        f"  摘要: {fc.get('summary','-')}"
        for fc in file_changes
    ) if file_changes else "(无文件变更)"

    l3_content = f"""[完整对话归档 L3] session={session_id} agent={agent_id} hash={content_hash}
时间: {ts} | 复杂度: {complexity}

【要素1: 完整用户消息】
{user_msg}

【要素2: Agent完整回复】
{agent_resp}

【要素3: 关键决策过程】
{dec_text}

【要素4: 所有文件变更】
{fc_text}"""

    if mcp_tools:
        l3_content += f"\n\n【MCP工具使用】{', '.join(mcp_tools)}"
    if tvp_decls:
        l3_content += "\n【TVP声明】\n" + "\n".join(tvp_decls)

    l3_id = safe_post_memory(
        l3_content, "episodic",
        ["conversation-archive", "full-capture", f"session:{session_id}",
         f"agent:{agent_id}", f"complexity:{complexity}", f"hash:{content_hash}"],
        "high" if complexity != "trivial" else "medium",
    )
    result["l3_id"] = l3_id

    # ── L4 Semantic: 每个文件变更一条 ──
    for fc in file_changes:
        fname = Path(fc.get("path", "")).name or fc.get("path", "unknown")
        l4_content = f"""[文件变更索引 L4] session={session_id}
时间: {ts}
文件: {fc.get('path','?')}
类型: {fc.get('type','modify')}
变更: +{fc.get('lines',0)}行
摘要: {fc.get('summary','-')}"""
        l4_id = safe_post_memory(
            l4_content, "semantic",
            ["file-sync", "full-capture", f"session:{session_id}",
             f"file:{fname}", f"change:{fc.get('type','modify')}"],
            "medium",
        )
        if l4_id:
            result["l4_ids"].append(l4_id)

    # ── L5 Meta: 仅critical级 ──
    if complexity == "critical" and decisions:
        dec_summary = "\n".join(
            f"- {d.get('step','?')} @{d.get('agent','?')}: {d.get('decision','?')}"
            for d in decisions
        )
        fc_summary = "\n".join(
            f"- {fc.get('path','?')} ({fc.get('type','modify')})"
            for fc in file_changes
        ) if file_changes else "无"

        l5_content = f"""[系统级决策归档 L5] session={session_id}
时间: {ts} | agent={agent_id}

【决策清单】
{dec_summary}

【影响文件】{len(file_changes)}个
{fc_summary}

【影响范围】Agent对话归档(方式A: HTTP POST到/api/memory/)"""
        l5_id = safe_post_memory(
            l5_content, "meta",
            ["system-decision", "full-capture", f"session:{session_id}",
             f"agent:{agent_id}"],
            "critical",
        )
        result["l5_id"] = l5_id

    result["offline_queued"] = sum(1 for e in ERRORS if "离线队列" in e)
    result["errors"] = ERRORS
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Agent对话归档工具 v2.0 (方式A: HTTP POST到/api/memory/)"
    )
    parser.add_argument(
        "input_file", nargs="?", default=None,
        help="JSON输入文件路径 (4要素)"
    )
    parser.add_argument("-i", "--input", default=None, help="同input_file")
    parser.add_argument("-s", "--session", default=None, help="会话ID")
    parser.add_argument("-u", "--user-message", default=None, help="用户消息(要素1)")
    parser.add_argument("-a", "--agent-response", default=None, help="Agent回复(要素2)")
    parser.add_argument("-d", "--decisions", default=None, help="决策JSON文件路径(要素3)")
    parser.add_argument("-f", "--file-changes", default=None, help="文件变更JSON文件路径(要素4)")
    parser.add_argument("-c", "--complexity", default="standard",
                        choices=["trivial", "standard", "critical"])
    parser.add_argument("--agent-id", default="tianji", help="Agent ID")
    parser.add_argument("--mcp-tools", default=None, help="MCP工具 逗号分隔")
    parser.add_argument("--tvp", default=None, help="TVP声明 逗号分隔")
    parser.add_argument("--json-output", action="store_true", default=True,
                        help="JSON格式输出(默认)")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 加载输入
    input_file = args.input_file or args.input

    if input_file:
        # 从JSON文件加载
        with open(input_file, "r", encoding="utf-8") as f:
            input_data = json.load(f)
        input_data.setdefault("session_id",
            input_data.get("session_id") or f"archive-{int(time.time())}")
    elif args.session:
        # 从命令行参数构造
        decisions = []
        file_changes = []
        if args.decisions:
            with open(args.decisions, "r", encoding="utf-8") as f:
                decisions = json.load(f)
        if args.file_changes:
            with open(args.file_changes, "r", encoding="utf-8") as f:
                file_changes = json.load(f)

        mcp_tools = args.mcp_tools.split(",") if args.mcp_tools else []
        tvp = args.tvp.split(",") if args.tvp else []

        input_data = {
            "session_id": args.session,
            "user_message": args.user_message or "",
            "agent_response": args.agent_response or "",
            "agent_id": args.agent_id,
            "complexity": args.complexity,
            "decisions": decisions,
            "file_changes": file_changes,
            "mcp_tools": mcp_tools,
            "tvp_declarations": tvp,
        }
    else:
        # 从stdin读JSON
        stdin_data = sys.stdin.read()
        if stdin_data.strip():
            input_data = json.loads(stdin_data)
        else:
            parser.error("必须提供input_file、-i参数、-s参数或stdin JSON输入")
            sys.exit(1)

    input_data.setdefault("session_id", f"archive-{int(time.time())}")
    input_data.setdefault("agent_id", "tianji")
    input_data.setdefault("complexity", "standard")

    # 执行归档
    if args.verbose:
        print(f"归档中... session={input_data['session_id']} "
              f"complexity={input_data.get('complexity')} "
              f"files={len(input_data.get('file_changes', []))}",
              file=sys.stderr)

    result = archive(input_data)

    # 输出
    if args.verbose:
        print(f"L3: {result['l3_id']}", file=sys.stderr)
        print(f"L4: {len(result['l4_ids'])}条", file=sys.stderr)
        print(f"L5: {result['l5_id']}", file=sys.stderr)
        print(f"离线队列: {result['offline_queued']}", file=sys.stderr)
        if ERRORS:
            for e in ERRORS:
                print(f"错误: {e}", file=sys.stderr)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
