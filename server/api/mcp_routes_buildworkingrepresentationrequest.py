# -*- coding: utf-8-sig -*-
"""mcp_routes_BuildWorkingRepresentationRequest — 从 mcp_routes.py 拆分 (SSS-PhaseB)

源文件: mcp_routes.py
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from server.api.utils import run_sync as _run
from server.deps import get_cognition, get_engine


class BuildWorkingRepresentationRequest(BaseModel):
    query: str
    agent_type: str = "general"
    observer: str | None = None
    subject: str | None = None
    session_key: str | None = None
    max_items: int = 24
    include_raw: bool = False
    include_digests: bool = True
    include_derived: bool = True
    include_contradictions: bool = True


__all__ = ["BuildWorkingRepresentationRequest"]
