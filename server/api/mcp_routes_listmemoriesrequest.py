# -*- coding: utf-8-sig -*-
"""mcp_routes_ListMemoriesRequest — 从 mcp_routes.py 拆分 (SSS-PhaseB)

源文件: mcp_routes.py
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from server.api.utils import run_sync as _run
from server.deps import get_cognition, get_engine


class ListMemoriesRequest(BaseModel):
    agent_type: str = "general"
    category: str | None = None
    limit: int = 50
    offset: int = 0


__all__ = ["ListMemoriesRequest"]
