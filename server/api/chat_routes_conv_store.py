# -*- coding: utf-8-sig -*-
"""chat_routes_conv_store.py — 从 chat_routes.py 拆分 (SSS-PhaseB)

conv_store功能组
源文件: chat_routes.py
"""

import asyncio
import json
import os
import time
import traceback
import uuid
from typing import AsyncGenerator, Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# [FIX-SSS] 拆分后模块级状态变量丢失，补回
import threading

_CONVERSATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "conversations")
_CONVERSATIONS_DIR = os.path.abspath(_CONVERSATIONS_DIR)
_CONVERSATIONS_INDEX = os.path.join(_CONVERSATIONS_DIR, "_index.json")
_conversations: Dict[str, Dict] = {}
_save_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(_CONVERSATIONS_DIR, exist_ok=True)


def _conv_file(conv_id: str) -> str:
    return os.path.join(_CONVERSATIONS_DIR, f"{conv_id}.json")


def _save_conversation(conv: Dict):
    """单对话文件持久化 — 每个对话独立文件, 避免全量写入"""
    _ensure_dir()
    try:
        with open(_conv_file(conv["id"]), "w", encoding="utf-8") as f:
            json.dump(conv, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _save_index():
    """保存对话索引 (轻量元数据, 不含消息体)"""
    _ensure_dir()
    try:
        index = {}
        for cid, conv in _conversations.items():
            index[cid] = {
                "id": conv["id"],
                "title": conv.get("title", "新对话"),
                "message_count": conv.get("message_count", 0),
                "total_tokens": conv.get("total_tokens", 0),
                "summary": conv.get("summary", ""),
                "created_at": conv.get("created_at", 0),
                "updated_at": conv.get("updated_at", 0),
                "pinned": conv.get("pinned", False),
            }
        with open(_CONVERSATIONS_INDEX, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_all_from_disk():
    """启动时从磁盘加载全部对话 — 保证服务重启后数据不丢失"""
    global _conversations
    _ensure_dir()
    loaded = {}

    # 优先从索引文件加载元数据
    if os.path.exists(_CONVERSATIONS_INDEX):
        try:
            with open(_CONVERSATIONS_INDEX, "r", encoding="utf-8") as f:
                index = json.load(f)
            for cid, meta in index.items():
                loaded[cid] = {
                    "id": meta["id"],
                    "title": meta.get("title", "新对话"),
                    "messages": [],
                    "total_tokens": meta.get("total_tokens", 0),
                    "summary": meta.get("summary", ""),
                    "created_at": meta.get("created_at", 0),
                    "updated_at": meta.get("updated_at", 0),
                    "message_count": meta.get("message_count", 0),
                    "pinned": meta.get("pinned", False),
                }
        except Exception:
            pass

    # 加载每个对话的完整消息
    for fname in os.listdir(_CONVERSATIONS_DIR):
        if not fname.endswith(".json") or fname == "_index.json":
            continue
        fpath = os.path.join(_CONVERSATIONS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                conv = json.load(f)
            cid = conv.get("id", "")
            if cid:
                loaded[cid] = conv
        except Exception:
            continue

    _conversations = loaded
    print(f"[ChatStore] 已从磁盘加载 {len(_conversations)} 个对话")


# 启动时自动加载
_load_all_from_disk()

