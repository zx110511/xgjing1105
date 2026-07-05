r"""
天机GraphRAG混合检索引擎 (Tianji Hybrid Retriever) v1.0
========================================================
向量检索 + 图谱扩展 + 关键词召回 三路融合

设计哲学:
  向量检索: 语义理解，快速入口点
  图谱扩展: 多跳推理，深度关联
  关键词召回: 精确匹配，补充覆盖
  RRF融合: 倒数排名融合，平衡准确率

架构位置: 天机/core/hybrid_retriever.py
依赖: graph_store, sqlite_store

灵境道谱溯源: D2-4【混合检索煞】· 道二·知枢体道 · 四地煞之知之术
"""

import time
import logging
import threading
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from .graph_store import TianjiGraphStore, KnowledgeTriple
from ..shared.knowledge_extractor import KnowledgeExtractor

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """检索结果"""
    entry_id: str
    content: str
    score: float
    source: str  # vector, graph, keyword
    metadata: Dict[str, Any]
    
    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "content": self.content,
            "score": self.score,
            "source": self.source,
            "metadata": self.metadata
        }


@dataclass
class HybridResult:
    """混合检索结果"""
    results: List[RetrievalResult]
    vector_count: int
    graph_count: int
    keyword_count: int
    retrieval_time: float
    fusion_method: str


class VectorRetriever:
    """向量检索器 (基于FTS5)"""
    
    def __init__(self, sqlite_store=None):
        self.sqlite_store = sqlite_store
    
    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        """向量检索"""
        if not self.sqlite_store:
            return []
        
        try:
            results = self.sqlite_store.search(query, limit=top_k)
            return [
                RetrievalResult(
                    entry_id=r.get("id", ""),
                    content=r.get("content", ""),
                    score=r.get("score", 0.5),
                    source="vector",
                    metadata=r
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return []


class GraphRetriever:
    """图谱检索器"""
    
    def __init__(self, graph_store: TianjiGraphStore, extractor: KnowledgeExtractor):
        self.graph_store = graph_store
        self.extractor = extractor
    
    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        hops: int = 2
    ) -> List[RetrievalResult]:
        """图谱检索"""
        try:
            extraction = self.extractor.extract(query, use_llm=False)
            
            if not extraction.entities:
                return []
            
            results = []
            seen_nodes = set()
            
            for entity in extraction.entities[:5]:
                node = self.graph_store.query_by_content(entity)
                
                if node and node.id not in seen_nodes:
                    seen_nodes.add(node.id)
                    
                    related = self.graph_store.multi_hop(node.id, hops=hops)
                    
                    for item in related:
                        node_id = item.get("node_id", "")
                        if node_id not in seen_nodes:
                            seen_nodes.add(node_id)
                            
                            node_data = item.get("node_data", {})
                            results.append(RetrievalResult(
                                entry_id=node_id,
                                content=node_data.get("content", ""),
                                score=item.get("confidence", 0.5) * 0.9,
                                source="graph",
                                metadata={
                                    "relation": item.get("relation", ""),
                                    "depth": item.get("depth", 1)
                                }
                            ))
            
            results.sort(key=lambda x: x.score, reverse=True)
            return results[:top_k]
        except Exception as e:
            logger.error(f"图谱检索失败: {e}")
            return []


class KeywordRetriever:
    """关键词检索器 (BM25)"""
    
    def __init__(self, sqlite_store=None):
        self.sqlite_store = sqlite_store
    
    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        """关键词检索"""
        if not self.sqlite_store:
            return []
        
        try:
            keywords = query.split()
            results = []
            
            for keyword in keywords[:5]:
                if len(keyword) > 1:
                    keyword_results = self.sqlite_store.search(keyword, limit=top_k // 2)
                    for r in keyword_results:
                        results.append(RetrievalResult(
                            entry_id=r.get("id", ""),
                            content=r.get("content", ""),
                            score=r.get("score", 0.3) * 0.8,
                            source="keyword",
                            metadata={"keyword": keyword}
                        ))
            
            seen = set()
            unique_results = []
            for r in results:
                if r.entry_id not in seen:
                    seen.add(r.entry_id)
                    unique_results.append(r)
            
            unique_results.sort(key=lambda x: x.score, reverse=True)
            return unique_results[:top_k]
        except Exception as e:
            logger.error(f"关键词检索失败: {e}")
            return []


class HybridRetriever:
    """混合检索器"""
    
    def __init__(
        self,
        graph_store: TianjiGraphStore,
        sqlite_store=None,
        vector_weight: float = 0.5,
        graph_weight: float = 0.3,
        keyword_weight: float = 0.2
    ):
        self.graph_store = graph_store
        self.sqlite_store = sqlite_store
        
        self.extractor = KnowledgeExtractor()
        
        self.vector_retriever = VectorRetriever(sqlite_store)
        self.graph_retriever = GraphRetriever(graph_store, self.extractor)
        self.keyword_retriever = KeywordRetriever(sqlite_store)
        
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight
        self.keyword_weight = keyword_weight
        
        self._lock = threading.RLock()
    
    def reciprocal_rank_fusion(
        self,
        result_lists: List[List[RetrievalResult]],
        k: int = 60
    ) -> List[RetrievalResult]:
        """
        倒数排名融合 (Reciprocal Rank Fusion)
        
        RRF_score(d) = Σ 1 / (k + rank_i(d))
        """
        scores: Dict[str, Tuple[float, RetrievalResult]] = {}
        
        for results in result_lists:
            for rank, result in enumerate(results, start=1):
                entry_id = result.entry_id
                
                rrf_score = 1.0 / (k + rank)
                
                if entry_id in scores:
                    old_score, old_result = scores[entry_id]
                    scores[entry_id] = (old_score + rrf_score, old_result)
                else:
                    scores[entry_id] = (rrf_score, result)
        
        sorted_results = sorted(scores.values(), key=lambda x: x[0], reverse=True)
        
        return [result for score, result in sorted_results]
    
    def weighted_fusion(
        self,
        vector_results: List[RetrievalResult],
        graph_results: List[RetrievalResult],
        keyword_results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """加权融合"""
        scores: Dict[str, Tuple[float, RetrievalResult]] = {}
        
        for result in vector_results:
            weighted_score = result.score * self.vector_weight
            scores[result.entry_id] = (weighted_score, result)
        
        for result in graph_results:
            weighted_score = result.score * self.graph_weight
            if result.entry_id in scores:
                old_score, old_result = scores[result.entry_id]
                scores[result.entry_id] = (old_score + weighted_score, old_result)
            else:
                scores[result.entry_id] = (weighted_score, result)
        
        for result in keyword_results:
            weighted_score = result.score * self.keyword_weight
            if result.entry_id in scores:
                old_score, old_result = scores[result.entry_id]
                scores[result.entry_id] = (old_score + weighted_score, old_result)
            else:
                scores[result.entry_id] = (weighted_score, result)
        
        sorted_results = sorted(scores.values(), key=lambda x: x[0], reverse=True)
        return [result for score, result in sorted_results]
    
    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        hops: int = 2,
        fusion_method: str = "rrf"
    ) -> HybridResult:
        """
        混合检索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            hops: 图谱多跳深度
            fusion_method: 融合方法 (rrf, weighted)
        
        Returns:
            混合检索结果
        """
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_vector = executor.submit(
                self.vector_retriever.retrieve, query, top_k
            )
            future_graph = executor.submit(
                self.graph_retriever.retrieve, query, top_k, hops
            )
            future_keyword = executor.submit(
                self.keyword_retriever.retrieve, query, top_k
            )
            
            vector_results = future_vector.result()
            graph_results = future_graph.result()
            keyword_results = future_keyword.result()
        
        if fusion_method == "rrf":
            fused_results = self.reciprocal_rank_fusion(
                [vector_results, graph_results, keyword_results]
            )
        else:
            fused_results = self.weighted_fusion(
                vector_results, graph_results, keyword_results
            )
        
        final_results = fused_results[:top_k]
        
        return HybridResult(
            results=final_results,
            vector_count=len(vector_results),
            graph_count=len(graph_results),
            keyword_count=len(keyword_results),
            retrieval_time=time.time() - start_time,
            fusion_method=fusion_method
        )
    
    def retrieve_with_context(
        self,
        query: str,
        top_k: int = 10,
        context_window: int = 3
    ) -> Dict[str, Any]:
        """带上下文的检索"""
        hybrid_result = self.retrieve(query, top_k)
        
        enriched_results = []
        for result in hybrid_result.results:
            context = []
            
            if result.source == "graph":
                node = self.graph_store.query_by_content(result.content)
                if node:
                    related = self.graph_store.multi_hop(node.id, hops=1)
                    context = [
                        {
                            "content": r.get("node_data", {}).get("content", ""),
                            "relation": r.get("relation", "")
                        }
                        for r in related[:context_window]
                    ]
            
            enriched_results.append({
                **result.to_dict(),
                "context": context
            })
        
        return {
            "query": query,
            "results": enriched_results,
            "stats": {
                "vector_count": hybrid_result.vector_count,
                "graph_count": hybrid_result.graph_count,
                "keyword_count": hybrid_result.keyword_count,
                "retrieval_time": hybrid_result.retrieval_time,
                "fusion_method": hybrid_result.fusion_method
            }
        }
