# -*- coding: utf-8-sig -*-
"""
conversation_archiver.py — 完整对话归档器 v1.0
==============================================

实现"Agent视角完整内容归档"，取代摘要式归档。

归档4要素(强制):
  1. 完整用户消息 (user_message, 全文)
  2. Agent全部回复 (agent_response, 全文)
  3. 关键决策过程 (decisions, 列表)
  4. 所有文件变更 (file_changes, 列表)

归档策略:
  - L3 Episodic: 完整对话内容(4要素合并)
  - L4 Semantic: 文件变更索引(每文件一条)
  - L5 Meta: 系统级决策归档(可选)

集成路径:
  - HTTP API: POST /api/conversation/archive
  - 启动器集成: launcher/tianji_v91_launcher.py
  - 桌面快捷方式: start_tianji.bat → launcher → server → archiver

设计原则:
  - 完整记录,不摘要化 (信息密度100%)
  - 失败降级到离线队列
  - 幂等性(content_hash去重)
  - UTF-8-SIG全链路安全
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("tianji.conversation_archiver")

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TIANJI_API_URL = "http://127.0.0.1:8771"
OFFLINE_QUEUE = PROJECT_ROOT / ".tianji" / "offline_writes.json"


@dataclass
class Decision:
    """关键决策记录"""

    step: str  # 决策步骤(如 "Step1-识别")
    agent: str  # 决策Agent
    decision: str  # 决策内容
    reason: str = ""  # 决策原因
    evidence: str = ""  # 证据/数据

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "agent": self.agent,
            "decision": self.decision,
            "reason": self.reason,
            "evidence": self.evidence,
        }


@dataclass
class FileChange:
    """文件变更记录"""

    file_path: str
    change_type: str  # create/modify/delete
    summary: str = ""  # 变更摘要
    lines_added: int = 0
    lines_removed: int = 0
    diff_preview: str = ""  # 变更预览(前200字符)

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "change_type": self.change_type,
            "summary": self.summary,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "diff_preview": self.diff_preview[:200],
        }


@dataclass
class ConversationArchive:
    """完整对话归档(4要素)"""

    session_id: str
    turn_number: int
    user_message: str  # 完整用户消息
    agent_response: str  # Agent完整回复
    decisions: list[Decision] = field(default_factory=list)
    file_changes: list[FileChange] = field(default_factory=list)
    agent_id: str = "tianji"
    timestamp: float = field(default_factory=time.time)
    complexity: str = "standard"  # trivial/standard/critical
    mcp_tools_used: list[str] = field(default_factory=list)
    tvp_declarations: list[str] = field(default_factory=list)

    def __post_init__(self):
        # 计算content_hash用于幂等性
        raw = f"{self.session_id}:{self.turn_number}:{len(self.user_message)}:{len(self.agent_response)}"
        self.content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        self.total_bytes = len(self.user_message.encode("utf-8")) + len(
            self.agent_response.encode("utf-8")
        )

    def build_l3_content(self) -> str:
        """构建L3 Episodic层完整内容(4要素合并)"""
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))
        lines = []
        lines.append(
            f"[完整对话归档 L3] session={self.session_id} turn={self.turn_number} agent={self.agent_id}"
        )
        lines.append(
            f"时间: {ts} | 复杂度: {self.complexity} | hash: {self.content_hash}"
        )
        lines.append("")

        lines.append("【要素1: 完整用户消息】")
        lines.append(self.user_message)
        lines.append("")

        lines.append("【要素2: Agent完整回复】")
        lines.append(self.agent_response)
        lines.append("")

        lines.append("【要素3: 关键决策过程】")
        if self.decisions:
            for d in self.decisions:
                lines.append(f"  - {d.step} | @{d.agent} | {d.decision}")
                if d.reason:
                    lines.append(f"    原因: {d.reason}")
                if d.evidence:
                    lines.append(f"    证据: {d.evidence}")
        else:
            lines.append("  (无关键决策)")
        lines.append("")

        lines.append("【要素4: 所有文件变更】")
        if self.file_changes:
            for fc in self.file_changes:
                lines.append(
                    f"  - {fc.file_path} | {fc.change_type} | +{fc.lines_added}/-{fc.lines_removed}"
                )
                if fc.summary:
                    lines.append(f"    摘要: {fc.summary}")
        else:
            lines.append("  (无文件变更)")
        lines.append("")

        if self.mcp_tools_used:
            lines.append(f"【MCP工具使用】{', '.join(self.mcp_tools_used)}")
        if self.tvp_declarations:
            lines.append("【TVP声明】")
            for tvp in self.tvp_declarations:
                lines.append(f"  {tvp}")

        return "\n".join(lines)

    def build_l4_file_change_content(self, fc: FileChange) -> str:
        """构建L4 Semantic层文件变更索引内容"""
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))
        return (
            f"[文件变更索引 L4] session={self.session_id} turn={self.turn_number}\n"
            f"时间: {ts}\n"
            f"文件: {fc.file_path}\n"
            f"类型: {fc.change_type}\n"
            f"变更: +{fc.lines_added}/-{fc.lines_removed}\n"
            f"摘要: {fc.summary}\n"
            f"预览: {fc.diff_preview[:200]}"
        )

    def build_l5_decision_content(self) -> str:
        """构建L5 Meta层系统级决策内容(仅critical级)"""
        if self.complexity != "critical":
            return ""
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))
        lines = [
            f"[系统级决策归档 L5] session={self.session_id} turn={self.turn_number}",
            f"时间: {ts} | agent={self.agent_id}",
            "",
            "【决策清单】",
        ]
        for d in self.decisions:
            lines.append(f"  - {d.step} | @{d.agent} | {d.decision}")
            if d.reason:
                lines.append(f"    原因: {d.reason}")
        lines.append("")
        lines.append(f"【影响文件】{len(self.file_changes)}个")
        for fc in self.file_changes:
            lines.append(f"  - {fc.file_path} ({fc.change_type})")
        return "\n".join(lines)


class ConversationArchiver:
    """对话归档器 - 完整内容归档"""

    def __init__(self, api_url: str = TIANJI_API_URL):
        self.api_url = api_url
        self._lock = threading.Lock()
        self._stats = {
            "total_archives": 0,
            "total_bytes": 0,
            "l3_success": 0,
            "l4_success": 0,
            "l5_success": 0,
            "failures": 0,
            "offline_queued": 0,
        }

    def _http_post(self, path: str, data: dict, timeout: int = 30) -> dict | None:
        """HTTP POST请求(无代理)"""
        try:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                f"{self.api_url}{path}",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            # 创建无代理opener
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            r = opener.open(req, timeout=timeout)
            return json.loads(r.read().decode("utf-8", errors="replace"))
        except Exception as e:
            logger.warning(f"HTTP POST {path} 失败: {e}")
            return None

    def _write_offline_queue(self, item: dict) -> bool:
        """写入离线队列"""
        try:
            OFFLINE_QUEUE.parent.mkdir(parents=True, exist_ok=True)
            queue = []
            if OFFLINE_QUEUE.exists():
                queue = json.loads(OFFLINE_QUEUE.read_text(encoding="utf-8"))
            item["id"] = f"offline-{len(queue) + 1:03d}"
            item["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            queue.append(item)
            OFFLINE_QUEUE.write_text(
                json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return True
        except Exception as e:
            logger.error(f"写入离线队列失败: {e}")
            return False

    def archive(self, conv: ConversationArchive) -> dict[str, Any]:
        """归档完整对话(4要素)

        Returns:
            dict: {
                "l3_id": str|None,  # L3 Episodic记忆ID
                "l4_ids": List[str],  # L4 Semantic文件变更索引ID列表
                "l5_id": str|None,  # L5 Meta系统决策ID(critical级才有)
                "offline_queued": int,  # 离线队列数量
                "stats": dict
            }
        """
        result = {"l3_id": None, "l4_ids": [], "l5_id": None, "offline_queued": 0}
        with self._lock:
            # 1. L3 Episodic: 完整对话内容
            l3_content = conv.build_l3_content()
            l3_data = {
                "content": l3_content,
                "layer": "episodic",
                "tags": [
                    "conversation-archive",
                    "full-capture",
                    f"session:{conv.session_id}",
                    f"agent:{conv.agent_id}",
                    f"complexity:{conv.complexity}",
                    f"hash:{conv.content_hash}",
                ],
                "priority": "high" if conv.complexity != "trivial" else "medium",
                "use_llm": False,
            }
            l3_resp = self._http_post("/api/memory/", l3_data)
            if l3_resp and l3_resp.get("id"):
                result["l3_id"] = l3_resp["id"]
                self._stats["l3_success"] += 1
            else:
                self._write_offline_queue(l3_data)
                result["offline_queued"] += 1
                self._stats["offline_queued"] += 1

            # 2. L4 Semantic: 每个文件变更一条索引
            for fc in conv.file_changes:
                l4_content = conv.build_l4_file_change_content(fc)
                l4_data = {
                    "content": l4_content,
                    "layer": "semantic",
                    "tags": [
                        "file-sync",
                        "full-capture",
                        f"session:{conv.session_id}",
                        f"file:{Path(fc.file_path).name}",
                        f"change:{fc.change_type}",
                    ],
                    "priority": "medium",
                    "use_llm": False,
                }
                l4_resp = self._http_post("/api/memory/", l4_data)
                if l4_resp and l4_resp.get("id"):
                    result["l4_ids"].append(l4_resp["id"])
                    self._stats["l4_success"] += 1
                else:
                    self._write_offline_queue(l4_data)
                    result["offline_queued"] += 1
                    self._stats["offline_queued"] += 1

            # 3. L5 Meta: 系统级决策(仅critical级)
            if conv.complexity == "critical":
                l5_content = conv.build_l5_decision_content()
                if l5_content:
                    l5_data = {
                        "content": l5_content,
                        "layer": "meta",
                        "tags": [
                            "system-decision",
                            "full-capture",
                            f"session:{conv.session_id}",
                            f"agent:{conv.agent_id}",
                        ],
                        "priority": "critical",
                        "use_llm": False,
                    }
                    l5_resp = self._http_post("/api/memory/", l5_data)
                    if l5_resp and l5_resp.get("id"):
                        result["l5_id"] = l5_resp["id"]
                        self._stats["l5_success"] += 1
                    else:
                        self._write_offline_queue(l5_data)
                        result["offline_queued"] += 1
                        self._stats["offline_queued"] += 1

            # 更新统计
            self._stats["total_archives"] += 1
            self._stats["total_bytes"] += conv.total_bytes

        return result

    def get_stats(self) -> dict:
        """获取归档器统计"""
        with self._lock:
            return dict(self._stats)


# 全局单例
_archiver: ConversationArchiver | None = None
_archiver_lock = threading.Lock()


def get_archiver() -> ConversationArchiver:
    """获取归档器单例"""
    global _archiver
    if _archiver is None:
        with _archiver_lock:
            if _archiver is None:
                _archiver = ConversationArchiver()
    return _archiver
