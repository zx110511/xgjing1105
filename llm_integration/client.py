r"""
DeepSeek记忆系统客户端 — 同步+异步双模
=========================================
DeepSeek LLM作为天机v9.1唯一大脑中枢。

特性:
- 异步底层 (httpx) + 同步封装 (asyncio.run) 供engine直调
- 自动重试 (最多3次)
- JSON提取 (markdown代码块兼容)
- 超时控制
"""

import asyncio
import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class DeepSeekConfig:
    api_key: str
    base_url: str = "https://api.deepseek.com/v1"
    # DeepSeek-V4-Pro: deepseek-chat模型支持1M输入上下文, 64K最大输出
    model: str = "deepseek-chat"
    timeout: int = 120  # 1M上下文场景需要更长超时
    max_retries: int = 3
    temperature: float = 0.3
    max_tokens: int = 65536  # DeepSeek V4 Pro 最大输出 64K tokens
    enable_cache: bool = True
    cache_ttl: int = 1800
    # V4双模式: "v4-pro" (复杂推理/Thinking) | "v4-flash" (高性价比/快速)
    model_mode: str = "v4-flash"
    # Thinking模式开关 (仅V4-Pro支持完整Thinking输出)
    thinking_enabled: bool = False
    # 推理强度: "low" | "medium" | "high"
    reasoning_effort: str = "medium"

    # 模型名称映射 — mode -> 实际API模型名
    _MODEL_NAME_MAP: Dict[str, str] = None  # type: ignore

    def __post_init__(self) -> None:
        # dataclass类变量初始化 (避免mutable default)
        if self._MODEL_NAME_MAP is None:
            object.__setattr__(self, "_MODEL_NAME_MAP", {
                "v4-pro": "deepseek-v4-pro",
                "v4-flash": "deepseek-v4-flash",
            })

    def _get_model_name(self, mode: Optional[str] = None) -> str:
        """根据模式返回实际API模型名称 — L11路径唯一性法则

        Args:
            mode: 模型模式 ("v4-pro" | "v4-flash"), None则使用self.model_mode
        Returns:
            实际API模型名称
        """
        target_mode = mode or self.model_mode
        name_map = self._MODEL_NAME_MAP or {
            "v4-pro": "deepseek-v4-pro",
            "v4-flash": "deepseek-v4-flash",
        }
        return name_map.get(target_mode, self.model)

    @classmethod
    def from_env(cls) -> "DeepSeekConfig":
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        k = key.strip()
                        v = value.strip()
                        # [FIX-L01-EXCEPTION-20260628] .env优先覆盖系统环境变量占位符
                        # 原因: Python不支持shell变量展开, 系统环境变量可能残留占位符(如sk-your-api-key-here)
                        # 修复: .env中直接写入真实密钥, 非空且非shell语法值覆盖环境变量
                        # 安全: .env已被.gitignore排除, 不会提交到版本库
                        if v and not v.startswith("${"):
                            os.environ[k] = v
        # 解析Thinking开关 (L14拼写精确: 严格匹配 "true"/"1")
        _thinking_raw = os.getenv("DEEPSEEK_THINKING_ENABLED", "false").strip().lower()
        _thinking_enabled = _thinking_raw in ("true", "1", "yes", "on")
        # 解析推理强度 (L14拼写精确: 限定合法值)
        _effort = os.getenv("DEEPSEEK_REASONING_EFFORT", "medium").strip().lower()
        if _effort not in ("low", "medium", "high"):
            _effort = "medium"
        # 解析默认模式 (L14拼写精确: 限定合法值)
        _mode = os.getenv("DEEPSEEK_DEFAULT_MODE", "v4-flash").strip().lower()
        if _mode not in ("v4-pro", "v4-flash"):
            _mode = "v4-flash"
        return cls(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            timeout=int(os.getenv("LLM_TIMEOUT", "120")),
            max_tokens=int(os.getenv("DEEPSEEK_MAX_TOKENS", "65536")),
            model_mode=_mode,
            thinking_enabled=_thinking_enabled,
            reasoning_effort=_effort,
        )


class DeepSeekClient:
    def __init__(self, config: Optional[DeepSeekConfig] = None):
        self.config = config or DeepSeekConfig.from_env()
        self._async_client: Optional[httpx.AsyncClient] = None
        self._sync_cache: Dict[str, tuple[float, Any]] = {}
        # 真实 token 用量计数器 (会话累计, 来源于DeepSeek API usage字段)
        self.token_stats: Dict[str, int] = {"input": 0, "output": 0, "total": 0}
        self._token_lock = threading.Lock()

    def _record_usage(self, result: Dict[str, Any]) -> None:
        """从 API 响应的 usage 字段累计真实 token 用量。"""
        try:
            usage = result.get("usage") or {}
            pt = int(usage.get("prompt_tokens", 0) or 0)
            ct = int(usage.get("completion_tokens", 0) or 0)
            if pt or ct:
                with self._token_lock:
                    self.token_stats["input"] += pt
                    self.token_stats["output"] += ct
                    self.token_stats["total"] += pt + ct
        except Exception:
            pass

    @property
    def is_ready(self) -> bool:
        return bool(self.config.api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.config.timeout)
        return self._async_client

    async def close(self):
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None

    def _cache_key(self, system_prompt: str, user_prompt: str) -> str:
        raw = f"{self.config.model}:{system_prompt[:100]}:{user_prompt[:500]}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def chat(
        self,
        user_prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        expect_json: bool = True,
    ) -> Dict[str, Any]:
        if self.config.enable_cache:
            key = self._cache_key(system_prompt, user_prompt)
            cached = self._sync_cache.get(key)
            if cached and time.time() - cached[0] < self.config.cache_ttl:
                return cached[1]

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature
            if temperature is not None
            else self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }

        last_error = ""
        for attempt in range(self.config.max_retries):
            try:
                client = await self._get_client()
                response = await client.post(
                    f"{self.config.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                self._record_usage(result)
                content = result["choices"][0]["message"]["content"]

                parsed = self._parse_response(content, expect_json)

                if self.config.enable_cache and "error" not in parsed:
                    key = self._cache_key(system_prompt, user_prompt)
                    self._sync_cache[key] = (time.time(), parsed)

                return parsed

            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                if e.response.status_code == 429:
                    await asyncio.sleep(2**attempt)
                    continue
                break
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = f"Connection: {e}"
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                break

        return {"error": last_error, "success": False}

    def chat_sync(
        self, user_prompt: str, system_prompt: str = "", expect_json: bool = True
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        last_error = ""
        for attempt in range(self.config.max_retries):
            try:
                with httpx.Client(timeout=self.config.timeout) as client:
                    response = client.post(
                        f"{self.config.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()
                    self._record_usage(result)
                    content = result["choices"][0]["message"]["content"]
                    return self._parse_response(content, expect_json)
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                if e.response.status_code == 429:
                    time.sleep(2**attempt)
                    continue
                break
            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
                if attempt < self.config.max_retries - 1:
                    time.sleep(1)
                    continue
                break
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                break

        return {"error": last_error, "success": False}

    async def chat_with_mode(
        self,
        messages: List[Dict[str, str]],
        model_mode: str = "v4-flash",
        thinking_enabled: bool = False,
        reasoning_effort: str = "medium",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """V4双模式对话 — 支持 V4-Pro Thinking 模式 (L18增量开发: 不影响现有chat方法)

        Args:
            messages: 消息列表 (OpenAI格式: [{"role":..., "content":...}])
            model_mode: "v4-pro" | "v4-flash"
            thinking_enabled: 是否启用Thinking (仅V4-Pro有效)
            reasoning_effort: "low" | "medium" | "high"
            temperature: 温度参数, None则使用config默认值
            max_tokens: 最大tokens, None则使用config默认值
        Returns:
            {content, reasoning_content(仅V4-Pro+Thinking), usage, model_mode, success}
        """
        # L14拼写精确: 校验mode合法值
        if model_mode not in ("v4-pro", "v4-flash"):
            model_mode = "v4-flash"
        if reasoning_effort not in ("low", "medium", "high"):
            reasoning_effort = "medium"

        # L11路径唯一性: 通过config._get_model_name获取实际模型名
        model_name = self.config._get_model_name(model_mode)

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }

        # V4-Pro Thinking模式: 注入extra_body (L06数据契约对齐)
        # 仅当mode=v4-pro且thinking_enabled=True时启用
        if model_mode == "v4-pro" and thinking_enabled:
            payload["extra_body"] = {
                "thinking": {"type": "enabled"},
                "reasoning_effort": reasoning_effort,
            }
            # DeepSeek API接受顶层reasoning_effort (兼容两种格式)
            payload["reasoning_effort"] = reasoning_effort

        last_error = ""
        for attempt in range(self.config.max_retries):
            try:
                client = await self._get_client()
                response = await client.post(
                    f"{self.config.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                self._record_usage(result)

                msg = result.get("choices", [{}])[0].get("message", {})
                content = msg.get("content", "")
                # V4-Pro Thinking模式返回reasoning_content字段
                reasoning_content = msg.get("reasoning_content", "") if thinking_enabled else ""

                return {
                    "content": content,
                    "reasoning_content": reasoning_content,
                    "usage": result.get("usage", {}),
                    "model_mode": model_mode,
                    "model": model_name,
                    "success": True,
                }
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                if e.response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
                break
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = f"Connection: {e}"
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                break
        return {"error": last_error, "success": False, "model_mode": model_mode}

    @staticmethod
    def _parse_response(content: str, expect_json: bool) -> Any:
        if not expect_json:
            return {"content": content, "success": True}

        text = content.strip()
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start) if "```" in text[start:] else len(text)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start) if "```" in text[start:] else len(text)
            text = text[start:end].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            for line in reversed(text.split("\n")):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
            if text.startswith("[") and text.endswith("]"):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
            return {"content": content, "raw_response": text, "success": True}
