r"""
语义搜索路由 v6.0 — 专用线程池
v6.0: 统一工具函数 (utils.py) + 消除重复代码
"""

import traceback

from fastapi import APIRouter, Query

from core.shared.models import MemoryResponse, MemorySearchQuery
from server.api.utils import run_sync as _run
from server.api.utils import safe_memory_response as _safe_memory_response


def _to_dict(entry):
    return entry if isinstance(entry, dict) else entry.to_dict()


def _get_id(entry):
    return entry.get("id", "") if isinstance(entry, dict) else entry.id


def create_search_router(embeddings_service=None):
    router = APIRouter()

    def _op_log(action: str, detail: str):
        try:
            from server.main import _log_operation

            _log_operation("memory", action, detail)
        except Exception:
            pass

    @router.get("/")
    async def search_root(q: str = "", limit: int = 20):
        from server.deps import engine

        entries = await _run(
            engine.recall, query=q if q else None, limit=limit, min_score=0.0
        )
        _op_log("search", f"query={q[:50]} results={len(entries)}")
        return [_safe_memory_response(e) for e in entries]

    @router.post("/", response_model=list[MemoryResponse])
    async def search_memory(query: MemorySearchQuery):
        from server.deps import engine

        entries = await _run(
            engine.recall,
            query=query.query,
            layers=query.layers,
            tags=query.tags,
            priority=query.priority,
            limit=query.limit,
            min_score=query.min_score,
            include_archived=query.include_archived,
        )
        if query.semantic and embeddings_service:
            try:
                sr = await _run(
                    embeddings_service.semantic_search, query.query, limit=query.limit
                )
                sids = {r["id"] for r in sr}
                entries = [e for e in entries if _get_id(e) in sids] + [
                    e for e in entries if _get_id(e) not in sids
                ]
            except Exception:
                pass
        return [_safe_memory_response(e) for e in entries]

    @router.get("/quick", response_model=list[MemoryResponse])
    async def quick_search(
        q: str = Query(...),
        layer: str | None = Query(None),
        limit: int = Query(20, ge=1, le=100),
    ):
        from server.deps import engine

        entries = await _run(
            engine.recall,
            query=q,
            layers=[layer] if layer else None,
            limit=limit,
            min_score=0.0,
        )
        return [_safe_memory_response(e) for e in entries]

    @router.get("/semantic")
    async def semantic_search(
        q: str = Query(..., description="搜索查询词"),
        limit: int = Query(20, ge=1, le=100),
        layer: str | None = Query(None),
        threshold: float = Query(0.0, ge=0.0, le=1.0),
    ):
        """语义搜索 - GET版本，返回与POST一致的包装格式"""
        from server.deps import engine

        if embeddings_service:
            try:
                results = await _run(embeddings_service.semantic_search, q, limit=limit)
                return {"results": results, "total": len(results), "query_time": 0}
            except Exception:
                pass
        try:
            entries = await _run(
                engine.recall,
                query=q,
                layers=[layer] if layer else None,
                limit=limit,
                min_score=threshold,
            )
            results = []
            for e in entries:
                d = e if isinstance(e, dict) else e.to_dict()
                results.append(
                    {"memory": d, "score": d.get("score", 0.5), "highlights": []}
                )
            return {"results": results, "total": len(results), "query_time": 0}
        except Exception as exc:
            traceback.print_exc()
            from fastapi import HTTPException

            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/semantic")
    async def semantic_search_post(body: dict):
        from fastapi import HTTPException

        from server.deps import engine

        query = body.get("query", body.get("q", ""))
        limit = body.get("limit", 20)
        threshold = body.get("threshold", 0.0)
        layer = body.get("layer")
        if embeddings_service:
            try:
                results = await _run(
                    embeddings_service.semantic_search, query, limit=limit
                )
                return {"results": results, "total": len(results), "query_time": 0}
            except Exception:
                pass
        try:
            entries = await _run(
                engine.recall,
                query=query,
                layers=[layer] if layer else None,
                limit=limit,
                min_score=threshold,
            )
            results = []
            for e in entries:
                d = e if isinstance(e, dict) else e.to_dict()
                results.append(
                    {"memory": d, "score": d.get("score", 0.5), "highlights": []}
                )
            return {"results": results, "total": len(results), "query_time": 0}
        except Exception as exc:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/by-tag/{tag}", response_model=list[MemoryResponse])
    async def search_by_tag(tag: str, limit: int = Query(20, ge=1, le=100)):
        from server.deps import engine

        entries = await _run(engine.recall, tags=[tag], limit=limit, min_score=0.0)
        return [_safe_memory_response(e) for e in entries]

    @router.get("/index/status")
    async def index_status():
        if not embeddings_service:
            try:
                from server.deps import engine

                stats = await _run(engine.stats)
                return {
                    "status": "sqlite_fts",
                    "indexed": stats.get("total_entries", 0),
                    "total": stats.get("total_entries", 0),
                    "backend": "sqlite_fts5",
                }
            except Exception:
                return {"status": "not_available", "indexed": 0, "total": 0}
        return {"status": "ready", **(await _run(embeddings_service.get_index_stats))}

    @router.post("/index/rebuild")
    async def rebuild_index():
        if not embeddings_service:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=503, detail="Embedding service not available"
            )
        count = await _run(embeddings_service.rebuild_index)
        return {"status": "rebuilding", "entries_to_index": count}

    @router.post("/fusion")
    async def fusion_search(body: dict):
        """
        四通道融合检索 — FTS5→tag_index→语义→KG
        """
        from server.deps import get_fusion_retriever

        query = body.get("query", body.get("q", ""))
        limit = body.get("limit", 20)
        layers = body.get("layers")
        min_score = body.get("min_score", 0.0)
        if not query:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="query is required")
        retriever = get_fusion_retriever()
        if not retriever:
            from fastapi import HTTPException

            raise HTTPException(status_code=503, detail="FusionRetriever not available")
        result = await _run(
            retriever.retrieve,
            query=query,
            limit=limit,
            layers=layers,
            min_score=min_score,
        )
        return {
            "results": result.results,
            "channel_stats": result.channel_stats,
            "total_time_ms": round(result.total_time_ms, 2),
            "fusion_method": result.fusion_method,
            "total_results": len(result.results),
        }

    @router.get("/fusion/stats")
    async def fusion_stats():
        from server.deps import get_fusion_retriever

        retriever = get_fusion_retriever()
        if not retriever:
            return {"status": "not_available"}
        return retriever.get_stats()

    return router
