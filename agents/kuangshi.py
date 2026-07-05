"""
矿师 — L2 语料处理Agent
==========================
语料导入、数据清洗、分类标注、批量处理。

灵境道谱溯源: D4-2【数据杂质煞】· 道四·记忆体道
位置: agents/kuangshi.py
MCP归属: memory-engine-global
绑定工具: memory_remember, execute_command, memory_recall, tianji_auto_tag, tianji_classify
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class KuangshiAgent:

    AGENT_ID = "kuangshi"

    QUALITY_CHECKS = {
        "empty": lambda x: bool(x and x.strip()),
        "min_length": lambda x: len(x) >= 10,
        "max_length": lambda x: len(x) <= 10000,
        "encoding": lambda x: True,
    }

    LABEL_TEMPLATES = {
        "sentiment": ["正面", "负面", "中性"],
        "domain": ["技术", "文学", "管理", "安全", "其他"],
        "quality": ["高", "中", "低"],
    }

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._corpus: List[Dict[str, Any]] = []
        self._batches: Dict[str, Dict[str, Any]] = {}

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        action = getattr(task, "action", "import")
        payload = getattr(task, "payload", {})
        print(f"[TVP] {self.emoji} {self.name}(L2) 语料处理: {action}")

        handlers = {
            "import": self.import_corpus,
            "clean": self.clean_data,
            "label": self.batch_label,
            "tag": self.auto_tag,
            "classify": self.auto_classify,
        }
        handler = handlers.get(action, self.import_corpus)
        return handler(payload)

    def import_corpus(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        items = payload.get("items", [])
        source = payload.get("source", "unknown")
        imported = 0
        skipped = 0
        for item in items:
            entry = {
                "id": f"corpus_{len(self._corpus)}",
                "content": item if isinstance(item, str) else item.get("content", ""),
                "source": source,
                "imported_at": time.time(),
                "labels": [],
                "tags": [],
                "quality_score": 0.0,
            }
            self._corpus.append(entry)
            imported += 1
        print(f"[TVP] {self.emoji} 矿师: 导入 {imported} 条语料 (跳过 {skipped})")
        return {"status": "imported", "imported": imported, "skipped": skipped, "total": len(self._corpus)}

    def clean_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        target_ids = payload.get("ids")
        entries = self._corpus if target_ids is None else [
            e for e in self._corpus if e["id"] in target_ids
        ]
        cleaned = 0
        for entry in entries:
            original = entry["content"]
            cleaned_content = self._clean_text(original)
            if cleaned_content != original:
                entry["content"] = cleaned_content
                cleaned += 1
        return {"status": "cleaned", "cleaned_count": cleaned, "total_processed": len(entries)}

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('\u200b', '').replace('\ufeff', '')
        text = text.strip()
        return text

    def batch_label(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        label_type = payload.get("label_type", "sentiment")
        labels = payload.get("labels", self.LABEL_TEMPLATES.get(label_type, ["默认"]))
        target_ids = payload.get("ids")
        entries = self._corpus if target_ids is None else [
            e for e in self._corpus if e["id"] in target_ids
        ]
        labeled = 0
        for entry in entries:
            assigned_label = labels[hash(entry["content"]) % len(labels)]
            entry["labels"].append({"type": label_type, "value": assigned_label})
            labeled += 1
        return {"status": "labeled", "label_type": label_type, "labeled_count": labeled}

    def auto_tag(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        target_ids = payload.get("ids")
        entries = self._corpus if target_ids is None else [
            e for e in self._corpus if e["id"] in target_ids
        ]
        tag_rules = [
            ("python", ["python", "def ", "import ", "class "]),
            ("config", ["config", "yaml", "json", "toml"]),
            ("agent", ["Agent", "agent", "MCP", "编排"]),
            ("memory", ["记忆", "memory", "recall", "remember"]),
            ("security", ["安全", "security", "密码", "密钥"]),
        ]
        tagged = 0
        for entry in entries:
            content = entry["content"].lower()
            new_tags = [tag for tag, keywords in tag_rules
                        if any(kw.lower() in content for kw in keywords)]
            entry["tags"] = list(set(entry.get("tags", []) + new_tags))
            tagged += 1
        return {"status": "tagged", "tagged_count": tagged}

    def auto_classify(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        target_ids = payload.get("ids")
        entries = self._corpus if target_ids is None else [
            e for e in self._corpus if e["id"] in target_ids
        ]
        categories = {
            "技术文档": ["代码", "API", "函数", "模块", "配置"],
            "创意写作": ["故事", "角色", "情节", "世界", "场景"],
            "管理记录": ["任务", "进度", "团队", "计划", "决策"],
            "安全审计": ["漏洞", "合规", "密码", "权限", "审计"],
        }
        classified = 0
        for entry in entries:
            content = entry["content"]
            scores = {cat: sum(1 for kw in kws if kw in content)
                      for cat, kws in categories.items()}
            best = max(scores, key=scores.get) if any(scores.values()) else "其他"
            entry["classification"] = best
            classified += 1
        return {"status": "classified", "classified_count": classified}

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "corpus_size": len(self._corpus),
            "batches_count": len(self._batches),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }