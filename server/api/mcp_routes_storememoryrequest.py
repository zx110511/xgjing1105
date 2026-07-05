# -*- coding: utf-8-sig -*-
"""mcp_routes_StoreMemoryRequest — 从 mcp_routes.py 拆分 (SSS-PhaseB)

源文件: mcp_routes.py
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from server.api.utils import run_sync as _run
from server.deps import get_cognition, get_engine


class StoreMemoryRequest(BaseModel):
    content: str
    agent_type: str = "general"
    category: str = "general"
    labels: list[str] = []
    metadata: dict[str, Any] = {}


__all__ = ["StoreMemoryRequest"]
