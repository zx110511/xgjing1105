r"""
天机v9.1 - Trae IDE 适配器
=============================
为 Trae IDE 提供标准化的记忆接入接口
兼容现有 MCP memory-engine 协议，可无缝替换
"""

import os
import time
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from .base import PlatformAdapter, MemorySDKConfig


class TraeAdapter(PlatformAdapter):
    def __init__(self, config: MemorySDKConfig = None):
        if config is None:
            config = MemorySDKConfig(platform="trae")
        super().__init__(config)
        self._conversation_buffer: List[Dict] = []
        self._buffer_max = 20

    def get_platform_info(self) -> Dict[str, str]:
        return {
            "platform": "trae",
            "version": "1.0.0",
            "ide": os.environ.get("TRAE_IDE_VERSION", "Trae IDE"),
            "adapter_version": "3.0.0",
        }

    def on_event(self, event_type: str, payload: Dict[str, Any]) -> Dict:
        handlers = {
            "message_received": self._on_message,
            "agent_switch": self._on_agent_switch,
            "file_changed": self._on_file_change,
            "session_start": self._on_session_start,
            "session_end": self._on_session_end,
        }
        handler = handlers.get(event_type, self._on_generic_event)
        return handler(payload)

    def _on_message(self, payload: Dict) -> Dict:
        content = payload.get("content", "")
        agent = payload.get("agent", "unknown")
        result = self.remember(
            content=content,
            layer="sensory",
            tags=["trae-message", f"agent:{agent}", "auto-collected"],
            priority="low",
            metadata={
                "agent": agent,
                "role": payload.get("role", ""),
                "conversation_id": payload.get("conversation_id", ""),
            },
        )
        return {"status": "stored", "entry_id": result.get("entry_id") if result else None}

    def _on_agent_switch(self, payload: Dict) -> Dict:
        result = self.remember(
            content=f"[Agent切换] {payload.get('from_agent', '?')} → {payload.get('to_agent', '?')}: {payload.get('task', '')}",
            layer="working",
            tags=["agent-switch", "tvp-trace", f"agent:{payload.get('to_agent', '')}"],
            priority="medium",
            metadata=payload,
        )
        return {"status": "stored", "entry_id": result.get("entry_id") if result else None}

    def _on_file_change(self, payload: Dict) -> Dict:
        result = self.remember(
            content=f"[文件变更] {payload.get('file_path', '')}: {payload.get('change_type', 'modified')}",
            layer="working",
            tags=["file-change", "auto-collected"],
            priority="low",
            metadata=payload,
        )
        return {"status": "stored", "entry_id": result.get("entry_id") if result else None}

    def _on_session_start(self, payload: Dict) -> Dict:
        result = self.remember(
            content=f"[会话开始] {payload.get('session_id', '')}",
            layer="episodic",
            tags=["session", "session-start"],
            priority="high",
            metadata=payload,
        )
        return {"status": "stored", "entry_id": result.get("entry_id") if result else None}

    def _on_session_end(self, payload: Dict) -> Dict:
        self.flush_batch()
        result = self.remember(
            content=f"[会话结束] {payload.get('session_id', '')}: {payload.get('summary', '')}",
            layer="episodic",
            tags=["session", "session-end", "summary"],
            priority="high",
            metadata=payload,
        )
        return {"status": "stored", "entry_id": result.get("entry_id") if result else None}

    def _on_generic_event(self, payload: Dict) -> Dict:
        self.send_event("generic", payload)
        return {"status": "forwarded"}

    def create_snapshot(self, name: str, data: Dict) -> Optional[Dict]:
        return self.remember(
            content=json.dumps(data, ensure_ascii=False, default=str),
            layer="episodic",
            tags=["snapshot", f"snapshot:{name}"],
            priority="high",
            metadata={"snapshot_name": name},
        )

    def query_by_agent(self, agent_name: str, limit: int = 50) -> Optional[List[Dict]]:
        return self.recall(f"agent:{agent_name}", limit=limit)

    def get_conversation_context(self, conversation_id: str) -> Optional[List[Dict]]:
        return self.recall(conversation_id, limit=100)

    def health_check_extended(self) -> Dict:
        base = self.health_check() or {}
        return {
            **base,
            "adapter": self.get_platform_info(),
            "server": f"{self.config.base_url}",
        }


def create_trae_adapter(base_url: str = "http://127.0.0.1:8771") -> TraeAdapter:
    config = MemorySDKConfig(
        base_url=base_url,
        platform="trae",
        timeout=10,
        retry_count=2,
        auto_batch=True,
        batch_size=30,
        batch_interval=3.0,
    )
    return TraeAdapter(config)
