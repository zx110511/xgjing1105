r"""
天机v9.1 - 自动摘要引擎
=========================
基于统计的抽取式摘要, 不依赖外部LLM
支持中文分句、关键词提取、决策识别
"""

import re
import time
from typing import List, Dict, Optional
from collections import Counter


class AutoSummarizer:
    def __init__(self):
        self._cn_stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
            '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
            '你', '会', '着', '没有', '看', '好', '自己', '这', '他', '她',
            '它', '们', '那', '些', '什么', '怎么', '如何', '可以', '这个',
            '那个', '还', '把', '被', '让', '给', '对', '从', '为', '以',
            '啊', '吧', '呢', '吗', '哦', '嗯', '哈',
        }

        self._decision_patterns = [
            re.compile(r'(决定|决策|确认|选择|采纳|采用|最终方案|推荐)([^。！？\n]{10,80})'),
            re.compile(r'(优先|执行|立即|批准|通过)([^。！？\n]{10,80})'),
            re.compile(r'([^。！？\n]{5,30})(方案|计划|策略|方向|路径)([^。！？\n]{5,50})'),
        ]

    def summarize(self, text: str, max_length: int = 500, language: str = "zh") -> str:
        if not text:
            return ""

        sentences = self._split_sentences(text, language)
        if not sentences:
            return text[:max_length]

        if len(sentences) <= 3:
            return "。".join(sentences) + "。"

        word_freq = self._compute_word_frequency(sentences)

        scored = []
        for i, sentence in enumerate(sentences):
            score = sum(word_freq.get(w, 0) for w in self._tokenize(sentence))
            position_score = 1.2 if i < len(sentences) * 0.2 else (
                0.7 if i > len(sentences) * 0.8 else 1.0
            )
            scored.append((score * position_score, i, sentence))

        scored.sort(reverse=True)
        top_n = max(3, min(10, int(len(sentences) * 0.3)))
        top_sentences = sorted(scored[:top_n], key=lambda x: x[1])

        summary = "。".join([s[2] for s in top_sentences]) + "。"
        if len(summary) > max_length:
            summary = summary[:max_length - 3].rstrip("。，,;；!！?？") + "..."

        return summary

    def extract_key_points(self, text: str, max_points: int = 8) -> List[str]:
        sentences = self._split_sentences(text)
        if not sentences:
            return []

        word_freq = self._compute_word_frequency(sentences)
        scored = []
        for i, s in enumerate(sentences):
            if len(s) < 8 or len(s) > 200:
                continue
            score = sum(word_freq.get(w, 0) for w in self._tokenize(s))
            scored.append((score, s))

        scored.sort(reverse=True)
        points = []
        seen = set()
        for _, s in scored[:max_points * 2]:
            key = s[:20]
            if key not in seen:
                points.append(s)
                seen.add(key)
            if len(points) >= max_points:
                break

        return points

    def extract_decisions(self, text: str) -> List[Dict[str, str]]:
        decisions = []
        for pattern in self._decision_patterns:
            for match in pattern.finditer(text):
                snippet = match.group(0).strip()
                keyword = match.group(1) if match.lastindex else "决策"
                decisions.append({
                    "keyword": keyword,
                    "snippet": snippet[:200],
                })

        seen = set()
        unique = []
        for d in decisions:
            if d["snippet"][:30] not in seen:
                unique.append(d)
                seen.add(d["snippet"][:30])
            if len(unique) >= 10:
                break

        return unique

    def extract_entities(self, text: str) -> List[str]:
        entities = set()

        patterns = [
            r'@(\w{2,20})',
            r'#(\w{2,20})',
            r'【(.+?)】',
            r'「(.+?)」',
            r'《(.+?)》',
            r'"(.*?)"',
            r'"(.*?)"',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text):
                entity = match.group(1).strip()
                if 2 <= len(entity) <= 30:
                    entities.add(entity)

        return list(entities)[:20]

    def _split_sentences(self, text: str, language: str = "zh") -> List[str]:
        if language == "zh":
            raw = re.split(r'[。！？\n]+', text)
        else:
            raw = re.split(r'[.!?\n]+', text)
        return [s.strip() for s in raw if len(s.strip()) > 3]

    def _tokenize(self, text: str) -> List[str]:
        words = []
        for w in text.split():
            w = w.strip("，,。.！!？?：:；;\"\"''（）()【】[]")
            if len(w) >= 2 and w not in self._cn_stop_words:
                words.append(w)
        for i in range(len(text) - 1):
            bigram = text[i:i+2]
            if bigram not in self._cn_stop_words and not any(
                c in "，。！？：；""''（）" for c in bigram
            ):
                words.append(bigram)
        return words

    def _compute_word_frequency(self, sentences: List[str]) -> Dict[str, int]:
        all_words = []
        for s in sentences:
            all_words.extend(self._tokenize(s))
        counter = Counter(all_words)
        max_freq = max(counter.values()) if counter else 1
        return {w: c / max_freq for w, c in counter.items()}
