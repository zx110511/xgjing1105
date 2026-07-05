"""
天算 — L2 数据分析师Agent
=============================
统计分析、可视化、模式识别、报告撰写。

灵境道谱溯源: D8-1【数据盲区煞】· 道八·数据体道
位置: agents/tiansuan.py
MCP归属: memory-engine-global
绑定工具: memory_recall, memory_stats, tianji_summarize, tianji_semantic_search
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class TiansuanAgent:

    AGENT_ID = "tiansuan"

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._reports: List[Dict[str, Any]] = []
        self._datasets: Dict[str, List[Any]] = {}

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        action = getattr(task, "action", "analyze")
        payload = getattr(task, "payload", {})
        print(f"[TVP] {self.emoji} {self.name}(L2) 数据分析: {action}")

        handlers = {
            "analyze": self.analyze_stats,
            "visualize": self.visualize_data,
            "pattern": self.recognize_patterns,
            "report": self.generate_report,
        }
        handler = handlers.get(action, self.analyze_stats)
        return handler(payload)

    def analyze_stats(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("data", [])
        if not isinstance(data, list) or not data:
            return {"status": "no_data"}

        numeric = [x for x in data if isinstance(x, (int, float))]
        if not numeric:
            return {"status": "no_numeric_data", "sample": data[:5]}

        n = len(numeric)
        mean = sum(numeric) / n
        sorted_data = sorted(numeric)
        median = sorted_data[n // 2] if n % 2 else (sorted_data[n//2 - 1] + sorted_data[n//2]) / 2
        variance = sum((x - mean) ** 2 for x in numeric) / n
        std_dev = variance ** 0.5

        return {
            "status": "analyzed",
            "count": n,
            "mean": round(mean, 4),
            "median": round(median, 4),
            "std_dev": round(std_dev, 4),
            "min": sorted_data[0],
            "max": sorted_data[-1],
            "range": sorted_data[-1] - sorted_data[0],
        }

    def visualize_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("data", [])
        chart_type = payload.get("chart_type", "ascii_bar")
        if not data:
            return {"status": "no_data"}

        numeric = [x for x in data if isinstance(x, (int, float))]
        if not numeric:
            return {"status": "no_numeric_data"}

        max_val = max(numeric)
        bars = []
        for i, val in enumerate(numeric):
            bar_len = int(val / max_val * 40) if max_val > 0 else 0
            bars.append(f"  [{i:3d}] {'█' * bar_len} {val}")
        ascii_chart = "\n".join(bars)

        return {
            "status": "visualized",
            "chart_type": chart_type,
            "data_points": len(numeric),
            "chart": ascii_chart,
        }

    def recognize_patterns(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("data", [])
        if not data:
            return {"status": "no_data"}

        numeric = [x for x in data if isinstance(x, (int, float))]
        patterns = []
        if len(numeric) >= 3:
            if all(numeric[i] <= numeric[i+1] for i in range(len(numeric)-1)):
                patterns.append("trend_upward")
            elif all(numeric[i] >= numeric[i+1] for i in range(len(numeric)-1)):
                patterns.append("trend_downward")
            else:
                patterns.append("fluctuating")

        return {
            "status": "analyzed",
            "patterns_detected": patterns,
            "data_points": len(numeric),
        }

    def generate_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        title = payload.get("title", "数据分析报告")
        data = payload.get("data", [])
        analysis = self.analyze_stats({"data": data}) if data else {"status": "no_data"}

        report = {
            "id": f"report_{len(self._reports)}",
            "title": title,
            "generated_at": time.time(),
            "sections": [
                {"title": "概述", "content": f"本报告分析 {len(data)} 个数据点"},
                {"title": "统计摘要", "content": analysis},
            ],
        }
        self._reports.append(report)
        return {"status": "generated", "report": report}

    def summarize(self, content: str, max_length: int = 200) -> str:
        if len(content) <= max_length:
            return content
        return content[:max_length-3] + "..."

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "reports_count": len(self._reports),
            "datasets_count": len(self._datasets),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
