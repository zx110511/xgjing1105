r"""
天机v9.1 - VSCode/Cursor 适配器 (骨架)
==========================================
为未来扩展到 VSCode 和 Cursor 预留标准接口
当前提供骨架实现，接入时只需实现平台特定逻辑
"""

from typing import Dict, Any, Optional, List
from .base import PlatformAdapter, MemorySDKConfig


class VSCodeAdapter(PlatformAdapter):
    def __init__(self, config: MemorySDKConfig = None):
        if config is None:
            config = MemorySDKConfig(platform="vscode")
        super().__init__(config)

    def get_platform_info(self) -> Dict[str, str]:
        return {
            "platform": "vscode",
            "version": "1.0.0-skeleton",
            "adapter_version": "3.0.0",
        }

    def on_event(self, event_type: str, payload: Dict[str, Any]) -> Dict:
        self.send_event(event_type, payload)
        return {"status": "forwarded"}

    def on_extension_message(self, message: Dict[str, Any]) -> Optional[Dict]:
        content = message.get("content", "")
        return self.remember(
            content=content,
            layer="sensory",
            tags=["vscode-extension", "auto-collected"],
            priority="low",
            metadata=message,
        )

    def on_completion_event(self, request: Dict, response: Dict) -> Optional[Dict]:
        return self.remember(
            content=f"[Completion] {request.get('prompt', '')[:200]} → {response.get('completion', '')[:200]}",
            layer="working",
            tags=["vscode-completion", "auto-collected"],
            priority="low",
            metadata={"request": str(request)[:500], "response": str(response)[:500]},
        )


class CursorAdapter(PlatformAdapter):
    def __init__(self, config: MemorySDKConfig = None):
        if config is None:
            config = MemorySDKConfig(platform="cursor")
        super().__init__(config)

    def get_platform_info(self) -> Dict[str, str]:
        return {
            "platform": "cursor",
            "version": "1.0.0-skeleton",
            "adapter_version": "3.0.0",
        }

    def on_event(self, event_type: str, payload: Dict[str, Any]) -> Dict:
        self.send_event(event_type, payload)
        return {"status": "forwarded"}

    def on_ai_interaction(self, prompt: str, response: str) -> Optional[Dict]:
        return self.remember(
            content=f"[Cursor AI] Prompt: {prompt[:300]} | Response: {response[:300]}",
            layer="episodic",
            tags=["cursor-ai", "auto-collected"],
            priority="medium",
            metadata={"prompt_length": len(prompt), "response_length": len(response)},
        )
