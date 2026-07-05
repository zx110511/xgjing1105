r"""
智能摘要路由 v6.0 — 专用线程池
v6.0: 统一工具函数 (utils.py) + 消除重复代码
"""

import time
from fastapi import APIRouter
from core.shared.models import SummaryRequest, SummaryResponse
from server.api.utils import run_sync as _run


def _val(entry, key, default=None):
    return entry.get(key, default) if isinstance(entry, dict) else getattr(entry, key, default)


def create_summary_router(embeddings_service=None):
    router = APIRouter()

    @router.get("/")
    def summary_root():
        return {"status": "active", "routes": ["POST /conversation", "GET /recent"],
                "engine": "extractive", "message": "智能摘要引擎运行中"}

    @router.post("/conversation", response_model=SummaryResponse)
    async def summarize_conversation(req: SummaryRequest):
        from server.deps import engine

        all_entries = await _run(engine.recall, limit=200, min_score=0.0)
        conv_entries = [e for e in all_entries
                         if req.conversation_id in str(_val(e, "metadata", {}).get("conversation_id", ""))
                         or req.conversation_id in _val(e, "tags", [])]

        if not conv_entries:
            conv_entries = [e for e in all_entries
                             if req.conversation_id in str(_val(e, "metadata", {}))]
        if not conv_entries:
            conv_entries = await _run(engine.recall, query=req.conversation_id, limit=50, min_score=0.0)
        if not conv_entries:
            from fastapi import HTTPException
            raise HTTPException(status_code=404,
                                 detail=f"No entries found for conversation: {req.conversation_id}")

        full_text = "\n".join([_val(e, "content", "") for e in conv_entries])
        summary = _extractive_summarize(full_text, req.max_length)
        key_points = _extract_key_points(conv_entries)
        decisions = _extract_decisions(conv_entries) if req.extract_decisions else []

        return SummaryResponse(conversation_id=req.conversation_id, summary=summary,
                                key_points=key_points, decisions=decisions,
                                entities=_extract_entities(full_text),
                                agent_contributions=_count_agent_contributions(conv_entries),
                                generated_at=time.time())

    @router.get("/recent")
    async def recent_summaries(limit: int = 10):
        from server.deps import engine
        meta_entries = await _run(engine.recall, layers=["meta"],
                                   tags=["summary", "conversation"], limit=limit, min_score=0.0)
        return [{"id": _val(e, "id", ""), "preview": _val(e, "content", "")[:300],
                  "created_at": _val(e, "created_at", 0), "tags": _val(e, "tags", [])}
                 for e in meta_entries]

    return router


def _extractive_summarize(text: str, max_length: int = 500) -> str:
    sentences = [s.strip() for s in text.replace("\n", " ").split("。") if len(s.strip()) > 5]
    if not sentences:
        sentences = [s.strip() for s in text.split("\n") if len(s.strip()) > 5]
    if not sentences:
        return text[:max_length]
    word_freq = {}
    for s in sentences:
        for w in s.split():
            if len(w) >= 2:
                word_freq[w] = word_freq.get(w, 0) + 1
    scored = []
    for i, s in enumerate(sentences):
        score = sum(word_freq.get(w, 0) for w in s.split() if len(w) >= 2)
        scored.append((score * (1.0 if i < len(sentences) * 0.3 else 0.8), i, s))
    scored.sort(reverse=True)
    top = sorted(scored[:max(3, min(10, len(scored) // 3))], key=lambda x: x[1])
    summary = "。".join([s[2] for s in top]) + "。"
    return summary[:max_length - 3] + "..." if len(summary) > max_length else summary


def _extract_key_points(entries) -> list:
    points = []
    for e in entries:
        if _val(e, "priority", "") in ("high", "critical"):
            points.append(_val(e, "content", "")[:100].replace("\n", " "))
    if not points:
        points = [_val(e, "content", "")[:80].replace("\n", " ") for e in entries[:5]]
    return list(dict.fromkeys(points))[:10]


def _extract_decisions(entries) -> list:
    kws = ["决定", "决策", "确认", "选择", "采纳", "采用",
           "最终方案", "推荐", "优先", "执行", "立即", "批准", "通过", "否决", "放弃"]
    decisions = []
    for e in entries:
        content = _val(e, "content", "")
        for kw in kws:
            if kw in content:
                idx = content.find(kw)
                start, end = max(0, idx - 30), min(len(content), idx + 100)
                decisions.append({"keyword": kw, "snippet": content[start:end].replace("\n", " ").strip(),
                                   "entry_id": _val(e, "id", "")})
                break
    return decisions[:10]


def _extract_entities(text: str) -> list:
    entities = set()
    for line in text.split("\n"):
        for ind in ["@", "#", "【", "】", "「", "」", "《", "》"]:
            if ind in line:
                for part in line.split(ind)[1:]:
                    w = part.split()[0] if part.split() else part[:10]
                    if 2 <= len(w) <= 20:
                        entities.add(w.strip(",:;，。；："))
    return list(entities)[:15]


def _count_agent_contributions(entries) -> dict:
    counts = {}
    for e in entries:
        m = _val(e, "metadata", {})
        agent = m.get("agent", m.get("platform", "unknown"))
        counts[agent] = counts.get(agent, 0) + 1
    return counts
