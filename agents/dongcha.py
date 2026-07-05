"""
洞察 — L1 上下文分析师Agent
=============================
意图识别、实体抽取、情感分析、关键词提取、语义搜索。

灵境道谱溯源: D2-3【上下文断裂煞】· 道二·理解体道
位置: agents/dongcha.py
MCP归属: agent-framework-global
绑定工具: context_extract, memory_recall, tianji_classify,
          tianji_summarize_conversation, tianji_intercept,
          tianji_extract_knowledge, tianji_expand_query, tianji_semantic_search
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory.amim import AgentMCPIntegrationManager, AgentDefinition


class DongchaAgent:

    AGENT_ID = "dongcha"

    INTENT_PATTERNS = {
        "create": ["创建", "新建", "生成", "写", "构建", "开发", "实现"],
        "query": ["查询", "搜索", "查找", "获取", "显示", "列出"],
        "modify": ["修改", "更新", "编辑", "更改", "重构", "优化"],
        "delete": ["删除", "移除", "清理", "清除"],
        "analyze": ["分析", "检查", "诊断", "审查", "评估"],
        "execute": ["运行", "执行", "启动", "部署", "发布"],
    }

    def __init__(self, amim: AgentMCPIntegrationManager):
        self.amim = amim
        self.defn: AgentDefinition = amim.get_agent(self.AGENT_ID)
        self._analysis_cache: Dict[str, Any] = {}

    @property
    def emoji(self) -> str:
        return self.defn.emoji

    @property
    def name(self) -> str:
        return self.defn.name

    def handle(self, task) -> Dict[str, Any]:
        text = getattr(task, "text", "") or getattr(task, "goal", "")
        print(f"[TVP] {self.emoji} {self.name}(L1) 分析上下文: {text[:80]}...")

        result = {
            "intent": self.analyze_intent(text),
            "entities": self.extract_entities(text),
            "keywords": self.extract_keywords(text),
            "sentiment": self.analyze_sentiment(text),
            "classification": self.classify(text),
        }

        cache_key = str(hash(text))[-12:]
        self._analysis_cache[cache_key] = result
        result["cache_key"] = cache_key
        return result

    def analyze_intent(self, text: str) -> Dict[str, Any]:
        scores = {}
        for intent, keywords in self.INTENT_PATTERNS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[intent] = score

        if not scores:
            return {"primary": "unknown", "confidence": 0.0, "scores": {}}

        primary = max(scores, key=scores.get)
        total = sum(scores.values())
        confidence = scores[primary] / total if total > 0 else 0.0
        return {"primary": primary, "confidence": round(confidence, 2), "scores": scores}

    def extract_entities(self, text: str) -> List[Dict[str, str]]:
        entities = []

        file_pattern = re.compile(r'[\w/\\]+\.(?:py|json|md|yaml|yml|toml|cfg|ini|exe|dll)')
        for match in file_pattern.finditer(text):
            entities.append({"type": "file_path", "value": match.group()})

        url_pattern = re.compile(r'https?://[^\s]+')
        for match in url_pattern.finditer(text):
            entities.append({"type": "url", "value": match.group()})

        agent_pattern = re.compile(r'@(铁卫|忆库|洞察|律令|灵犀|天枢|文宗|经纬|妙笔|明镜|天算|矿师|百巧|史官|锦书|千里|工造|镇山|追光)')
        for match in agent_pattern.finditer(text):
            entities.append({"type": "agent_mention", "value": match.group(1)})

        module_pattern = re.compile(r'M\d{1,2}')
        for match in module_pattern.finditer(text):
            entities.append({"type": "module_ref", "value": match.group()})

        return entities

    def extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        stop_words = {"的", "了", "是", "在", "和", "或", "与", "对", "为", "等",
                      "这", "那", "有", "不", "也", "就", "都", "而", "及", "但",
                      "the", "a", "an", "is", "are", "of", "in", "to", "for", "and"}
        words = re.findall(r'[\u4e00-\u9fff\w]+', text)
        filtered = [w for w in words if w.lower() not in stop_words and len(w) > 1]
        freq: Dict[str, int] = {}
        for w in filtered:
            freq[w] = freq.get(w, 0) + 1
        return sorted(freq, key=freq.get, reverse=True)[:top_n]

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        positive = ["好", "优秀", "成功", "正确", "完美", "通过", "完成"]
        negative = ["错误", "失败", "问题", "异常", "崩溃", "警告", "bug", "error"]

        pos_score = sum(1 for w in positive if w in text.lower())
        neg_score = sum(1 for w in negative if w in text.lower())

        if pos_score > neg_score:
            label = "positive"
        elif neg_score > pos_score:
            label = "negative"
        else:
            label = "neutral"

        return {"label": label, "positive_score": pos_score, "negative_score": neg_score}

    def classify(self, text: str) -> Dict[str, Any]:
        categories = {
            "代码": ["代码", "函数", "类", "模块", "导入", "def ", "class ", "import "],
            "文档": ["文档", "说明", "注释", "README", "doc"],
            "配置": ["配置", "config", "设置", "参数", "端口"],
            "错误": ["错误", "异常", "失败", "error", "exception", "bug"],
            "命令": ["运行", "执行", "启动", "命令", "run", "exec"],
            "架构": ["架构", "设计", "模式", "层", "模块", "architecture"],
        }

        scores = {}
        for cat, keywords in categories.items():
            scores[cat] = sum(1 for kw in keywords if kw.lower() in text.lower())

        if not any(scores.values()):
            return {"primary": "其他", "scores": {}}

        primary = max(scores, key=scores.get)
        return {"primary": primary, "scores": scores}

    def summarize(self, text: str, max_length: int = 200) -> str:
        if len(text) <= max_length:
            return text
        sentences = re.split(r'[。！？.!?\n]', text)
        summary = ""
        for s in sentences:
            if len(summary) + len(s) + 1 > max_length:
                break
            if s.strip():
                summary += s.strip() + "。"
        return summary

    def extract_knowledge(self, text: str) -> Dict[str, Any]:
        knowledge = {
            "facts": [],
            "definitions": [],
            "relationships": [],
        }

        fact_pattern = re.compile(r'([\u4e00-\u9fff\w]+)是([\u4e00-\u9fff\w]+)')
        for match in fact_pattern.finditer(text):
            knowledge["facts"].append({"subject": match.group(1), "predicate": match.group(2)})

        return knowledge

    def expand_query(self, query: str) -> List[str]:
        synonyms = {
            "升级": ["更新", "迁移", "改造", "优化"],
            "创建": ["新建", "生成", "构建", "开发"],
            "检查": ["验证", "审计", "审查", "诊断"],
            "配置": ["设置", "参数", "config"],
            "部署": ["发布", "上线", "deploy"],
        }
        expanded = [query]
        for key, syns in synonyms.items():
            if key in query:
                for syn in syns:
                    expanded.append(query.replace(key, syn))
        return expanded

    def interceptor_check(self, text: str) -> Dict[str, Any]:
        analysis = self.handle(type("Task", (), {"text": text, "goal": text}))
        needs_intercept = (
            analysis.get("sentiment", {}).get("label") == "negative" or
            len(analysis.get("keywords", [])) < 2
        )
        return {"needs_intercept": needs_intercept, "analysis": analysis}

    def health(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "name": self.name,
            "layer": f"L{self.defn.layer.value}",
            "status": "healthy",
            "cache_size": len(self._analysis_cache),
            "tools": self.defn.tools,
            "mcp_server": self.defn.mcp_server,
        }
