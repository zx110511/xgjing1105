r"""
天机灵境 gRPC Client v1.0
============================
灵境分布式就绪 — gRPC客户端 + 韧性保护

特性:
  - 自动服务发现(从ServiceRegistry获取目标地址)
  - CircuitBreaker保护(避免向故障服务发送请求)
  - RateLimiter控制(防止过载)
  - 自动重试 + 超时
  - Channel连接池复用

灵境道谱溯源: D8-9【通信未通煞】· 道八·通信体道 · 四地煞之序之术
"""

import time
import logging
import threading
from typing import Any, Optional, Dict, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

GRPC_AVAILABLE = False
try:
    import grpc
    GRPC_AVAILABLE = True
except ImportError:
    pass

PROTO_AVAILABLE = False
try:
    from proto import lingjing_pb2
    from proto import lingjing_pb2_grpc
    PROTO_AVAILABLE = True
except ImportError:
    pass


@dataclass
class GRPCClientConfig:
    host: str = "127.0.0.1"
    port: int = 8700
    timeout_seconds: float = 10.0
    max_retries: int = 2
    retry_backoff: float = 0.5
    use_tls: bool = False


class LingjingGRPCClient:
    """
    灵境gRPC客户端

    用法:
      client = LingjingGRPCClient(resilience=rm, registry=reg)
      result = client.remember("天机记忆内容", layer="episodic")
    """

    def __init__(
        self,
        config: GRPCClientConfig = None,
        resilience=None,
        registry=None,
        event_bus=None,
    ):
        self._config = config or GRPCClientConfig()
        self._resilience = resilience
        self._registry = registry
        self._event_bus = event_bus
        self._channel: Optional[grpc.Channel] = None
        self._stub_memory = None
        self._stub_registry = None
        self._stub_eventbus = None
        self._stub_agent = None
        self._lock = threading.Lock()
        self._connected = False

        if GRPC_AVAILABLE and PROTO_AVAILABLE:
            self._connect()

    def _connect(self):
        host = self._config.host
        port = self._config.port

        if self._registry:
            services = self._registry.discover(capability="memory")
            if services:
                svc = services[0]
                host = svc.host
                port = svc.port
                logger.info(f"gRPC service discovered: {svc.name} @ {host}:{port}")

        with self._lock:
            try:
                if self._config.use_tls:
                    creds = grpc.ssl_channel_credentials()
                    self._channel = grpc.secure_channel(f"{host}:{port}", creds)
                else:
                    self._channel = grpc.insecure_channel(f"{host}:{port}")
                self._stub_memory = lingjing_pb2_grpc.MemoryServiceStub(self._channel)
                self._stub_registry = lingjing_pb2_grpc.LingjingRegistryStub(self._channel)
                self._stub_eventbus = lingjing_pb2_grpc.LingjingEventBusStub(self._channel)
                self._stub_agent = lingjing_pb2_grpc.AgentServiceStub(self._channel)
                self._connected = True
                logger.info(f"gRPC client connected: {host}:{port}")
            except Exception as e:
                logger.warning(f"gRPC connect failed: {e}")
                self._connected = False

    def _call_with_resilience(self, service_id: str, fn: Callable, *args, **kwargs):
        if not self._connected:
            return None

        if self._resilience and not self._resilience.request(service_id):
            logger.warning(f"gRPC call blocked by resilience: {service_id}")
            return None

        last_error = None
        for attempt in range(self._config.max_retries + 1):
            try:
                result = fn(*args, **kwargs, timeout=self._config.timeout_seconds)
                if self._resilience:
                    self._resilience.success(service_id)
                return result
            except grpc.RpcError as e:
                last_error = e
                code = e.code()
                if code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                    if attempt < self._config.max_retries:
                        time.sleep(self._config.retry_backoff * (2 ** attempt))
                        continue
                break
            except Exception as e:
                last_error = e
                if attempt < self._config.max_retries:
                    time.sleep(self._config.retry_backoff)
                    continue
                break

        if self._resilience:
            self._resilience.failure(service_id)
        logger.warning(f"gRPC call failed after {self._config.max_retries+1} attempts: {last_error}")
        return None

    def remember(self, content: str, layer: str = "working", tags: list = None, priority: str = "medium") -> Optional[dict]:
        result = self._call_with_resilience("tianji-memory", self._stub_memory.Remember,
            lingjing_pb2.RememberRequest(content=content, layer=layer, tags=tags or [], priority=priority))
        if result:
            return {"memory_id": result.memory_id, "layer": result.layer, "gate_verdict": result.gate_verdict}
        return None

    def recall(self, query: str, layers: list = None, limit: int = 10) -> list:
        result = self._call_with_resilience("tianji-memory", self._stub_memory.Recall,
            lingjing_pb2.RecallRequest(query=query, layers=layers or [], limit=limit))
        if result:
            return [{"memory_id": it.memory_id, "content": it.content, "layer": it.layer,
                     "tags": list(it.tags), "score": it.score} for it in result.items]
        return []

    def classify(self, content: str, context: str = "") -> Optional[dict]:
        result = self._call_with_resilience("tianji-memory", self._stub_memory.Classify,
            lingjing_pb2.ClassifyRequest(content=content, context=context))
        if result:
            return {"recommended_layer": result.recommended_layer, "confidence": result.confidence}
        return None

    def extract_knowledge(self, content: str) -> list:
        result = self._call_with_resilience("tianji-memory", self._stub_memory.ExtractKnowledge,
            lingjing_pb2.ExtractKnowledgeRequest(content=content))
        if result:
            return [{"subject": t.subject, "relation": t.relation,
                     "object": t.object, "confidence": t.confidence} for t in result.triples]
        return []

    def health(self) -> Optional[dict]:
        result = self._call_with_resilience("tianji-memory", self._stub_memory.Health,
            lingjing_pb2.HealthRequest())
        if result:
            return {"status": result.status, "version": result.version,
                    "engine_ready": result.engine_ready, "uptime_seconds": result.uptime_seconds}
        return None

    def register_service(self, service_id: str, name: str, host: str, port: int,
                        layer: str = "L0", capabilities: list = None) -> bool:
        result = self._call_with_resilience("service-registry", self._stub_registry.Register,
            lingjing_pb2.RegisterRequest(
                service_id=service_id, name=name, host=host, port=port,
                layer=layer, capabilities=capabilities or [],
            ))
        return result.registered if result else False

    def discover_services(self, layer: str = None, capability: str = None) -> list:
        result = self._call_with_resilience("service-registry", self._stub_registry.Discover,
            lingjing_pb2.DiscoverRequest(layer=layer or "", capability=capability or ""))
        if result:
            return [{"service_id": s.service_id, "name": s.name, "host": s.host, "port": s.port,
                     "layer": s.layer, "capabilities": list(s.capabilities),
                     "status": s.status, "is_alive": s.is_alive} for s in result.services]
        return []

    def publish_event(self, event_type: str, source: str, payload: dict) -> Optional[str]:
        payload_json = __import__("json").dumps(payload, ensure_ascii=False)
        result = self._call_with_resilience("event-bus", self._stub_eventbus.Publish,
            lingjing_pb2.PublishRequest(event_type=event_type, source=source, payload_json=payload_json))
        return result.event_id if result else None

    def dispatch_task(self, task_type: str, task_data: dict, priority: str = "medium") -> Optional[dict]:
        task_data_json = __import__("json").dumps(task_data, ensure_ascii=False)
        result = self._call_with_resilience("agent-dispatch", self._stub_agent.Dispatch,
            lingjing_pb2.DispatchRequest(task_type=task_type, task_data_json=task_data_json, priority=priority))
        if result:
            return {"task_id": result.task_id, "agent_id": result.agent_id, "status": result.status}
        return None

    def list_agents(self) -> list:
        result = self._call_with_resilience("agent-dispatch", self._stub_agent.ListCapabilities,
            lingjing_pb2.ListCapabilitiesRequest())
        if result:
            return [{"agent_id": a.agent_id, "name": a.name, "layer": a.layer,
                     "capabilities": list(a.capabilities), "health_endpoint": a.health_endpoint}
                    for a in result.agents]
        return []

    @property
    def connected(self) -> bool:
        return self._connected

    def close(self):
        if self._channel:
            self._channel.close()
            self._connected = False

    def __del__(self):
        self.close()
