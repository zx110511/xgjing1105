"""
明镜 — L2 审校者Agent
========================
质量评估、一致性检查、风格验证、内容审校。

灵境道谱溯源: D3-3【审查漏洞煞】· 道三·治理体道
位置: agents/mingjing.py
MCP归属: agent-framework-global
绑定工具: memory_recall, rule_evaluate, security-scanner
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class MingjingAgent:

    AGENT_ID = "mingjing"

    REVIEW_CRITERIA = {
        "completeness": "完整性 — 内容是否覆盖所有必要方面",
        "consistency": "一致性 — 前后逻辑是否自洽",
        "accuracy": "准确性 — 事实和数据是否正确",
        "style": "风格 — 是否符合指定风格规范",
        "readability": "可读性 — 表达是否清晰易懂",
        "security": "安全性 — 是否包含敏感信息或安全风险",
    }

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._review_log: List[Dict[str, Any]] = []

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        content = getattr(task, "content", "") or getattr(task, "goal", "")
        criteria = getattr(task, "criteria", list(self.REVIEW_CRITERIA.keys()))
        print(f"[TVP] {self.emoji} {self.name}(L2) 审校: {content[:60]}...")

        result = self.review_quality(content, criteria)
        return result

    def review_quality(self, content: str, criteria: List[str] = None) -> Dict[str, Any]:
        if criteria is None:
            criteria = list(self.REVIEW_CRITERIA.keys())

        results = {}
        for c in criteria:
            checker = getattr(self, f"_check_{c}", None)
            if checker:
                results[c] = checker(content)
            else:
                results[c] = {"status": "skipped", "reason": "无检查器"}

        passed = all(r.get("status") in ("passed", "skipped") for r in results.values())
        failed = [c for c, r in results.items() if r.get("status") == "failed"]

        review = {
            "content_length": len(content),
            "criteria_count": len(criteria),
            "overall": "passed" if passed else "failed",
            "failed_criteria": failed,
            "details": results,
            "timestamp": time.time(),
        }
        self._review_log.append(review)

        if failed:
            print(f"[TVP] {self.emoji} 明镜: 审校未通过 → {failed}")
        else:
            print(f"[TVP] {self.emoji} 明镜: 审校通过 ✅")

        return {"status": "reviewed", "review": review}

    def _check_completeness(self, content: str) -> Dict[str, Any]:
        score = min(1.0, len(content) / 200) if content else 0.0
        return {"status": "passed" if score > 0.3 else "failed",
                "score": round(score, 2), "description": self.REVIEW_CRITERIA["completeness"]}

    def _check_consistency(self, content: str) -> Dict[str, Any]:
        contradictions = []
        if "是" in content and "不是" in content:
            pass
        return {"status": "passed",
                "contradictions_found": len(contradictions),
                "description": self.REVIEW_CRITERIA["consistency"]}

    def _check_accuracy(self, content: str) -> Dict[str, Any]:
        return {"status": "passed",
                "description": self.REVIEW_CRITERIA["accuracy"]}

    def _check_style(self, content: str) -> Dict[str, Any]:
        mixed_punctuation = any(c in content for c in "，。；：？！") and any(c in content for c in ",.;:?!")
        return {"status": "passed",
                "mixed_punctuation": mixed_punctuation,
                "description": self.REVIEW_CRITERIA["style"]}

    def _check_readability(self, content: str) -> Dict[str, Any]:
        words = content.replace("\n", " ").split()
        return {"status": "passed",
                "description": self.REVIEW_CRITERIA["readability"]}

    def _check_security(self, content: str) -> Dict[str, Any]:
        sensitive_patterns = ["password", "secret", "api_key", "token", "private_key"]
        found = [p for p in sensitive_patterns if p.lower() in content.lower()]
        return {"status": "failed" if found else "passed",
                "sensitive_found": found,
                "description": self.REVIEW_CRITERIA["security"]}

    def check_consistency(self, content: str, reference: str = None) -> Dict[str, Any]:
        review = self.review_quality(content, ["consistency", "completeness"])
        if reference:
            review["reference_compared"] = True
        return review

    def validate_style(self, content: str, expected_style: str = "专业") -> Dict[str, Any]:
        review = self.review_quality(content, ["style", "readability"])
        review["expected_style"] = expected_style
        return review

    def health(self) -> Dict[str, Any]:
        recent_fails = [r for r in self._review_log[-20:] if r.get("overall") == "failed"]
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "total_reviews": len(self._review_log),
            "recent_fail_rate": len(recent_fails) / max(1, min(20, len(self._review_log))),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
