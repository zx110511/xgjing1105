r"""
天机知识抽取引擎 (Tianji Knowledge Extractor) v1.0
========================================================
基于DeepSeek的知识三元组抽取

设计哲学:
  从非结构化文本中提取结构化知识
  三元组格式: (主体, 关系, 客体)
  支持多种关系类型和置信度评估

架构位置: 天机/core/knowledge_extractor.py
依赖: DeepSeek LLM

灵境道谱溯源: D2-2【实体抽取煞】· 道二·知枢体道 · 四地煞之知之术
"""

import re
import json
import time
import logging
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

from ..memory.graph_store import KnowledgeTriple

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """抽取结果"""
    triples: List[KnowledgeTriple]
    entities: List[str]
    confidence_avg: float
    extraction_time: float
    source_length: int


class KnowledgeExtractor:
    """知识抽取器"""

    RELATION_PATTERNS = {
        "is_a": [
            r"(.+?)是(?:一种|一个|一类)(.+)",
            r"(.+?)属于(.+)类别",
            r"(.+?)作为(.+)的一种",
        ],
        "has_part": [
            r"(.+?)包含(.+)",
            r"(.+?)由(.+)组成",
            r"(.+?)有(.+)部分",
        ],
        "causes": [
            r"(.+?)导致(.+)",
            r"(.+?)引起(.+)",
            r"(.+?)造成(.+)",
            r"(.+?)使得(.+)",
        ],
        "uses": [
            r"(.+?)使用(.+)",
            r"(.+?)采用(.+)",
            r"(.+?)利用(.+)",
        ],
        "belongs_to": [
            r"(.+?)属于(.+)",
            r"(.+?)归属于(.+)",
        ],
        "relates_to": [
            r"(.+?)与(.+)相关",
            r"(.+?)关联(.+)",
            r"(.+?)涉及(.+)",
        ],
        "depends_on": [
            r"(.+?)依赖(.+)",
            r"(.+?)取决于(.+)",
            r"(.+?)需要(.+)",
            r"(.+?)基于(.+)",
        ],
        "implements": [
            r"(.+?)实现(.+)",
            r"(.+?)执行(.+)",
            r"(.+?)完成了(.+)",
        ],
        "produces": [
            r"(.+?)产生(.+)",
            r"(.+?)输出(.+)",
            r"(.+?)生成(.+)",
            r"(.+?)构建(.+)",
        ],
        "configures": [
            r"(.+?)配置(.+)",
            r"(.+?)设置(.+)",
            r"(.+?)定义(.+)",
        ],
        "validates": [
            r"(.+?)验证(.+)",
            r"(.+?)检查(.+)",
            r"(.+?)审计(.+)",
        ],
    }

    def __init__(self, llm_driver=None):
        self.llm_driver = llm_driver
        self._cache: Dict[str, ExtractionResult] = {}

    def extract_with_patterns(self, text: str) -> List[KnowledgeTriple]:
        """基于模式的知识抽取"""
        triples = []

        for relation, patterns in self.RELATION_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    groups = match.groups()
                    if len(groups) >= 2:
                        subject = groups[0].strip()
                        obj = groups[1].strip()

                        if len(subject) > 2 and len(obj) > 2:
                            triples.append(KnowledgeTriple(
                                subject=subject,
                                relation=relation,
                                object=obj,
                                confidence=0.7,
                                evidence=match.group(0)
                            ))

        return triples

    def extract_with_llm(self, text: str, max_triples: int = 10) -> List[KnowledgeTriple]:
        """基于LLM的知识抽取"""
        if not self.llm_driver:
            logger.warning("LLM驱动未配置，回退到模式抽取")
            return self.extract_with_patterns(text)

        prompt = f"""从以下文本中抽取知识三元组，格式为JSON数组：
[{{"subject": "主体", "relation": "关系", "object": "客体", "confidence": 0.9}}]

文本：
{text}

关系类型：
- is_a: 是一个/一种
- has_part: 包含/组成
- causes: 导致/引起
- uses: 使用/采用
- belongs_to: 属于
- relates_to: 相关/关联

要求：
1. 只抽取明确表达的关系，不要推断
2. 置信度范围0.5-1.0
3. 最多抽取{max_triples}个三元组
4. 返回纯JSON，不要其他文字"""

        try:
            response = self.llm_driver.generate(prompt, temperature=0.3)

            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                triples_data = json.loads(json_match.group(0))

                triples = []
                for item in triples_data[:max_triples]:
                    if all(k in item for k in ["subject", "relation", "object"]):
                        triples.append(KnowledgeTriple(
                            subject=item["subject"].strip(),
                            relation=item["relation"],
                            object=item["object"].strip(),
                            confidence=item.get("confidence", 0.8),
                            evidence=text[:100]
                        ))

                return triples
        except Exception as e:
            logger.error(f"LLM抽取失败: {e}")

        return self.extract_with_patterns(text)

    def extract(
        self,
        text: str,
        use_llm: bool = True,
        max_triples: int = 10
    ) -> ExtractionResult:
        """完整的知识抽取"""
        start_time = time.time()

        cache_key = hashlib.md5(text.encode('utf-8')).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        if use_llm and self.llm_driver:
            triples = self.extract_with_llm(text, max_triples)
        else:
            triples = self.extract_with_patterns(text)

        entities = set()
        for triple in triples:
            entities.add(triple.subject)
            entities.add(triple.object)

        confidence_avg = 0.0
        if triples:
            confidence_avg = sum(t.confidence for t in triples) / len(triples)

        result = ExtractionResult(
            triples=triples,
            entities=list(entities),
            confidence_avg=confidence_avg,
            extraction_time=time.time() - start_time,
            source_length=len(text)
        )

        self._cache[cache_key] = result
        return result

    def validate_triple(self, triple: KnowledgeTriple) -> bool:
        """验证三元组有效性"""
        if not triple.subject or not triple.object:
            return False

        if len(triple.subject) < 2 or len(triple.object) < 2:
            return False

        if triple.relation not in self.RELATION_PATTERNS:
            return False

        if triple.confidence < 0.3 or triple.confidence > 1.0:
            return False

        return True

    def filter_triples(
        self,
        triples: List[KnowledgeTriple],
        min_confidence: float = 0.5
    ) -> List[KnowledgeTriple]:
        filtered = []
        for triple in triples:
            if self.validate_triple(triple) and triple.confidence >= min_confidence:
                filtered.append(triple)
        return filtered


class MultiPassFusionExtractor:
    """
    多Pass融合知识抽取器 v1.0

    设计哲学:
      单Pass抽取值不可靠，多Pass交叉验证+融合去重才可靠
      三个Pass:
        Pass 1 — 正则模式匹配 (覆盖面广, 精度低)
        Pass 2 — 关键词实体抽取 (实体识别+关系推断, 精度中)
        Pass 3 — LLM增强语义抽取 (精度高, 慢)
      融合策略: 多Pass一致→置信度提升, 单Pass独占→保守降权
    """

    FUSION_WEIGHTS = {
        "pattern": 0.45,
        "entity": 0.30,
        "llm": 0.25,
    }

    ENTITY_RELATION_KEYWORDS = {
        "contains": ["包含", "包括", "含有"],
        "depends_on": ["依赖", "需要", "基于"],
        "produces": ["生成", "创建", "输出"],
        "validates": ["验证", "检查", "审计"],
        "causes": ["导致", "引起", "触发"],
        "configures": ["配置", "设置", "修改"],
    }

    def __init__(self, base_extractor: Optional[KnowledgeExtractor] = None):
        self._base = base_extractor or KnowledgeExtractor()
        self._stats = {
            "total_fusions": 0,
            "pattern_only": 0,
            "entity_only": 0,
            "llm_only": 0,
            "multi_pass_agreed": 0,
            "conflicts_resolved": 0,
        }

    def extract_multi_pass(
        self,
        text: str,
        use_llm: bool = False,
        min_confidence: float = 0.4,
        max_triples: int = 20,
    ) -> ExtractionResult:
        import time
        start_time = time.time()

        pass1 = self._pass_pattern(text)
        pass2 = self._pass_entity_keywords(text)
        pass3 = []
        if use_llm and self._base.llm_driver:
            pass3 = self._pass_llm(text, max_triples)

        if not use_llm:
            self._stats["llm_only"] += 0
        elif pass3:
            self._stats["llm_only"] += len(pass3)

        fused = self._fuse(pass1, pass2, pass3)
        self._stats["total_fusions"] += 1

        filtered = self._base.filter_triples(fused, min_confidence)
        entities = set()
        for t in filtered:
            entities.add(t.subject)
            entities.add(t.object)

        conf_avg = sum(t.confidence for t in filtered) / max(len(filtered), 1)

        return ExtractionResult(
            triples=filtered[:max_triples],
            entities=list(entities),
            confidence_avg=round(conf_avg, 4),
            extraction_time=time.time() - start_time,
            source_length=len(text),
        )

    def _pass_pattern(self, text: str) -> List[KnowledgeTriple]:
        return self._base.extract_with_patterns(text)

    def _pass_entity_keywords(self, text: str) -> List[KnowledgeTriple]:
        triples = []
        for relation, keywords in self.ENTITY_RELATION_KEYWORDS.items():
            for kw in keywords:
                idx = text.find(kw)
                if idx < 0:
                    continue
                left = text[:idx].strip()
                right = text[idx + len(kw):].strip()

                subject = self._extract_entity_span(left, from_right=False)
                obj = self._extract_entity_span(right, from_right=True)

                if subject and obj and len(subject) > 1 and len(obj) > 1:
                    triples.append(KnowledgeTriple(
                        subject=subject,
                        relation=relation,
                        object=obj,
                        confidence=0.55,
                        evidence=f"{subject} {kw} {obj}",
                    ))
        return triples

    def _extract_entity_span(self, text: str, from_right: bool) -> str:
        if not text:
            return ""
        if from_right:
            parts = text.split()
            if not parts:
                return ""
            span = []
            for p in parts[:4]:
                if any(c in p for c in '，。；、！？{}[]()'):
                    break
                span.append(p)
            return " ".join(span).strip("，。；、！？{}[]()\"' ")
        else:
            parts = text.split()
            if not parts:
                return ""
            span = []
            for p in reversed(parts[-4:]):
                if any(c in p for c in '，。；、！？{}[]()'):
                    break
                span.insert(0, p)
            return " ".join(span).strip("，。；、！？{}[]()\"' ")

    def _pass_llm(self, text: str, max_triples: int) -> List[KnowledgeTriple]:
        return self._base.extract_with_llm(text, max_triples)

    def _fuse(
        self,
        pass1: List[KnowledgeTriple],
        pass2: List[KnowledgeTriple],
        pass3: List[KnowledgeTriple],
    ) -> List[KnowledgeTriple]:
        merged: Dict[str, KnowledgeTriple] = {}

        for t in pass1:
            key = f"{t.subject}|{t.relation}|{t.object}"
            merged[key] = t
            self._stats["pattern_only"] += 1

        for t in pass2:
            key = f"{t.subject}|{t.relation}|{t.object}"
            if key in merged:
                merged[key].confidence = min(
                    merged[key].confidence * (1.0 + self.FUSION_WEIGHTS["entity"]), 0.98
                )
                self._stats["multi_pass_agreed"] += 1
            else:
                merged[key] = t
                self._stats["entity_only"] += 1

        for t in pass3:
            key = f"{t.subject}|{t.relation}|{t.object}"
            if key in merged:
                merged[key].confidence = min(
                    merged[key].confidence * (1.0 + self.FUSION_WEIGHTS["llm"]), 0.99
                )
                self._stats["multi_pass_agreed"] += 1
            else:
                merged[key] = t

        normalized_key = {}
        for key, triple in merged.items():
            parts = key.split("|", 2)
            nk = f"{self._normalize(parts[0])}|{parts[1]}|{self._normalize(parts[2])}"
            if nk in normalized_key:
                existing = normalized_key[nk]
                if triple.confidence > existing.confidence:
                    normalized_key[nk] = triple
                    self._stats["conflicts_resolved"] += 1
            else:
                normalized_key[nk] = triple

        return list(normalized_key.values())

    def _normalize(self, text: str) -> str:
        import re
        text = re.sub(r'\s+', '', text)
        text = re.sub(r'[的得了着过]$', '', text)
        return text.lower()

    def get_fusion_stats(self) -> Dict[str, Any]:
        return dict(self._stats)


def tianji_extract_knowledge_enhanced(
    content: str,
    use_llm: bool = True,
    min_confidence: float = 0.5
) -> List[Tuple[str, str, str]]:
    """
    天机知识抽取增强版

    Args:
        content: 待抽取的文本内容
        use_llm: 是否使用LLM增强
        min_confidence: 最小置信度阈值

    Returns:
        知识三元组列表 [(主体, 关系, 客体), ...]
    """
    if not content or len(content) < 10:
        return []

    try:
        from .deepseek_driver import DeepSeekDriver
        llm_driver = DeepSeekDriver()
    except ImportError:
        llm_driver = None
        logger.warning("DeepSeek驱动未找到，使用模式抽取")

    extractor = KnowledgeExtractor(llm_driver)
    result = extractor.extract(content, use_llm=use_llm)

    filtered_triples = extractor.filter_triples(result.triples, min_confidence)

    return [t.to_tuple() for t in filtered_triples]


import hashlib
