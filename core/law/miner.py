# -*- coding: utf-8 -*-
"""
经验挖掘器 v2.0 — 从天机记忆中提取可提炼为法则的经验模式
[SSS-PhaseB] 从engine.py拆分

挖掘策略:
1. 规则匹配: 使用EXPERIENCE_MINING_PATTERNS正则匹配L3/L4内容
2. 频率聚合: 同类模式出现N次以上 → 高价值候选
3. 相似度聚类: 内容相似的记忆条目合并为一个经验模式
4. LLM增强: DeepSeek分析原始内容，提取结构化要素
5. 价值评分: 多维度评估(频率/影响/通用性/时效性)
"""

import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger("tianji.law_domain")

from .core import (
    ExperiencePattern,
    LawDomain,
    LawPriority,
    LawType,
)


class ExperienceMiner:
    """
    经验挖掘器 v2.0 — 从天机记忆中提取可提炼为法则的经验模式

    E3增强:
    - 连接天机REST API自动检索L3/L4/L5记忆
    - LLM深度提取(问题→根因→方案→预防→保障)
    - 经验价值评分排序
    - L3故障记录专项快速通道
    """

    def __init__(self, memory_api_url: str = "http://127.0.0.1:8771"):
        self._api_url = memory_api_url
        self._patterns: list[ExperiencePattern] = []
        self._stats = {
            "memories_scanned": 0,
            "patterns_found": 0,
            "high_frequency_patterns": 0,
            "already_covered_by_law": 0,
            "new_candidates": 0,
            "llm_extractions": 0,
            "value_scored": 0,
            "l3_fault_special": 0,
        }

    def fetch_memories_from_api(
        self,
        layers: list[str] = None,
        query: str = "故障 错误 教训 问题 经验",
        limit: int = 50,
    ) -> list[dict]:
        """E3增强: 从天机REST API检索记忆内容"""
        if layers is None:
            layers = ["episodic", "semantic", "meta"]

        all_memories = []
        for layer in layers:
            try:
                search_url = f"{self._api_url}/api/memory/search"
                params = urllib.parse.urlencode(
                    {
                        "query": query,
                        "layer": layer,
                        "limit": min(limit // len(layers), 20),
                        "include_content": "true",
                    }
                )
                full_url = f"{search_url}?{params}"

                req = urllib.request.Request(full_url, method="GET")
                req.add_header("Accept", "application/json")

                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if isinstance(data, dict) and "results" in data:
                        all_memories.extend(data["results"])
                    elif isinstance(data, list):
                        all_memories.extend(data)

                logger.debug(
                    f"[经验挖掘-API] {layer}层检索到 {len(all_memories)} 条记忆"
                )

            except urllib.error.HTTPError as e:
                logger.warning(f"[经验挖掘-API] HTTP错误 {e.code}: {e.reason}")
            except urllib.error.URLError as e:
                logger.warning(f"[经验挖掘-API] 连接失败: {e.reason}")
            except Exception as e:
                logger.warning(f"[经验挖掘-API] 异常: {type(e).__name__}: {e}")

        logger.info(
            f"[经验挖掘-API] 共检索到 {len(all_memories)} 条记忆 (layers={layers})"
        )
        return all_memories

    def mine_l3_fault_records(self, limit: int = 30) -> list[ExperiencePattern]:
        """E3增强: L3故障记录专项快速通道"""
        fault_query = "故障 错误 失败 bug 教训 根因 解决 修复 回滚 异常 Exception Error"
        memories = self.fetch_memories_from_api(
            layers=["episodic"], query=fault_query, limit=limit
        )

        fault_patterns = []
        for mem in memories:
            content = mem.get("content", "")
            mem_id = mem.get("id", "")
            tags = mem.get("tags", [])

            if not content or len(content) < 80:
                continue

            is_fault_record = any(
                kw in content.lower()
                for kw in [
                    "故障",
                    "错误",
                    "失败",
                    "bug",
                    "教训",
                    "根因",
                    "异常",
                    "error",
                    "exception",
                ]
            )

            if not is_fault_record:
                continue

            ep = ExperiencePattern(
                pattern_id=f"L3-FAULT-{hashlib.md5(mem_id.encode()).hexdigest()[:12]}",
                source_layer="episodic",
                source_id=mem_id,
                raw_content=content[:800],
                extracted_problem="",
                extracted_root_cause="",
                extracted_solution="",
                extracted_prevention="",
                domain_hint=LawDomain.PROCESS,
                type_hint=LawType.RECOVERY,
                priority_hint=LawPriority.P1_HIGH,
                is_fault_record=True,
                tags=list(tags),
            )
            fault_patterns.append(ep)
            self._stats["l3_fault_special"] += 1

        logger.info(f"[经验挖掘-L3专项] 发现 {len(fault_patterns)} 条故障记录")
        return fault_patterns

    def llm_deep_extract(self, pattern: ExperiencePattern) -> ExperiencePattern:
        """E3增强: 使用LLM深度提取经验要素"""
        try:
            from llm_integration.deepseek_driver import DeepSeekDriver

            driver = DeepSeekDriver()
            prompt = f"""你是一个经验提取专家。请从以下天机记忆内容中提取关键经验要素。

原始内容:
---
{pattern.raw_content}
---

请以JSON格式返回(严格JSON，不要其他文字):
{{
  "problem": "简洁描述遇到的问题(1句话)",
  "root_cause": "问题的根本原因是什么(1-2句话)",
  "solution": "如何解决的(2-3个步骤)",
  "prevention": "如何防止再次发生(1-2条具体措施)",
  "value_score": 1-10的整数(10最高，考虑:频率、影响范围、通用性),
  "suggested_domain": "process/path/memory/security/code_quality/deploy/agent之一",
  "suggested_type": "prevention/recovery/optimization/governance之一",
  "key_lessons": ["教训1", "教训2"]
}}"""

            response = driver.quick_decide(prompt)

            if response and isinstance(response, dict):
                pattern.extracted_problem = response.get("problem", "")
                pattern.extracted_root_cause = response.get("root_cause", "")
                pattern.extracted_solution = response.get("solution", "")
                pattern.extracted_prevention = response.get("prevention", "")
                pattern.value_score = int(response.get("value_score", 5))
                pattern.llm_enhanced = True

                domain_map = {
                    "process": LawDomain.PROCESS,
                    "path": LawDomain.PATH,
                    "memory": LawDomain.MEMORY,
                    "security": LawDomain.SECURITY,
                    "code_quality": LawDomain.CODE_QUALITY,
                    "deploy": LawDomain.DEPLOY,
                    "agent": LawDomain.AGENT,
                }
                suggested_domain = response.get("suggested_domain", "")
                if suggested_domain in domain_map:
                    pattern.domain_hint = domain_map[suggested_domain]

                type_map = {
                    "prevention": LawType.PREVENTION,
                    "recovery": LawType.RECOVERY,
                    "optimization": LawType.OPTIMIZATION,
                    "governance": LawType.GOVERNANCE,
                }
                suggested_type = response.get("suggested_type", "")
                if suggested_type in type_map:
                    pattern.type_hint = type_map[suggested_type]

                self._stats["llm_extractions"] += 1
                logger.debug(
                    f"[LLM提取] {pattern.pattern_id}: score={pattern.value_score}"
                )

        except ImportError:
            logger.warning("[LLM提取] DeepSeekDriver未安装，跳过LLM增强")
        except Exception as e:
            logger.warning(f"[LLM提取] 异常: {type(e).__name__}: {e}")

        return pattern

    def calculate_value_score(self, pattern: ExperiencePattern) -> int:
        """
        E3增强: 多维度价值评分 (总分10分)

        维度: 频率(0-3) + 影响(0-3) + 通用性(0-2) + 时效性(0-2) + LLM调整(±2)
        """
        score = 0

        freq_score = min(3, pattern.frequency // 2) if pattern.frequency > 0 else 0
        score += freq_score

        priority_scores = {
            LawPriority.P0_CRITICAL: 3,
            LawPriority.P1_HIGH: 2,
            LawPriority.P2_MEDIUM: 1,
            LawPriority.P3_LOW: 0,
        }
        score += priority_scores.get(pattern.priority_hint, 0)

        if pattern.is_fault_record or len(pattern.similar_pattern_ids) >= 3:
            score += 2
        elif len(pattern.similar_pattern_ids) >= 1:
            score += 1

        try:
            created = pattern.raw_content[:50]
            if any(kw in created for kw in ["2026", "2025"]):
                score += 2
        except (AttributeError, TypeError, IndexError):
            pass

        if pattern.value_score and pattern.value_score > 0:
            score = max(1, min(10, (score + pattern.value_score) // 2))

        pattern.value_score = score
        self._stats["value_scored"] += 1
        return score

    def mine_from_memory_contents(
        self, memories: list[dict], use_llm: bool = True, min_score: int = 3
    ) -> list[ExperiencePattern]:
        """从记忆内容列表中挖掘经验模式"""
        patterns: list[ExperiencePattern] = []
        self._stats["memories_scanned"] += len(memories)

        for mem in memories:
            content = mem.get("content", "")
            mem_id = mem.get("id", "")
            layer = mem.get("layer", "unknown")
            tags = mem.get("tags", [])

            if not content or len(content) < 50:
                continue

            ep = ExperiencePattern(
                pattern_id=f"EXP-{hashlib.md5(content.encode()).hexdigest()[:12]}",
                source_layer=layer,
                source_id=mem_id,
                raw_content=content[:800],
                domain_hint=LawDomain.PROCESS,
                type_hint=LawType.PREVENTION,
                priority_hint=LawPriority.P2_MEDIUM,
                tags=list(tags),
            )

            patterns.append(ep)
            self._stats["patterns_found"] += 1

        # 去重
        self._deduplicate_similar(patterns)

        # LLM深度提取
        if use_llm:
            for p in patterns[:20]:  # 限制LLM调用次数
                self.llm_deep_extract(p)

        # 价值评分
        for p in patterns:
            self.calculate_value_score(p)

        # 过滤低分
        scored = [p for p in patterns if p.value_score >= min_score]
        self._stats["new_candidates"] = len(scored)
        self._patterns.extend(scored)

        logger.info(
            f"[经验挖掘] 完成: {len(memories)}条记忆 → {len(patterns)}个模式 → {len(scored)}个候选(>={min_score}分)"
        )
        return scored

    def _deduplicate_similar(self, patterns: list[ExperiencePattern]):
        """基于内容哈希去重"""
        seen_content_hashes: set[str] = set()
        for p in patterns:
            content_hash = hashlib.md5(p.raw_content.encode()).hexdigest()[:16]
            if content_hash in seen_content_hashes:
                p.already_has_law = True
                self._stats["already_covered_by_law"] += 1
            seen_content_hashes.add(content_hash)

    def get_stats(self) -> dict:
        return dict(self._stats)
