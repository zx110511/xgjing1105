r"""
天机灵境 gRPC Server v1.0
============================
灵境分布式就绪 — gRPC通信层核心

将天机ICME记忆引擎暴露为gRPC服务，支持:
  - 23个Agent通过gRPC互相调用
  - ServiceRegistry注册+心跳
  - CircuitBreaker保护外部调用
  - EvolutionBus事件广播

启动方式:
  python -m core.grpc_server --port 8700 --service-id tianji-memory

灵境道谱溯源: D8-9【通信未通煞】· 道八·通信体道 · 四地煞之序之术
"""

import sys
import json
import time
import logging
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

GRPC_AVAILABLE = False
try:
    import grpc
    from grpc_reflection.v1alpha import reflection
    GRPC_AVAILABLE = True
except ImportError:
    pass

try:
    from proto import lingjing_pb2
    from proto import lingjing_pb2_grpc
    PROTO_AVAILABLE = True
except ImportError:
    PROTO_AVAILABLE = False


class TianjiGRPCServer:
    """
    天机gRPC服务端

    自动注册到ServiceRegistry, 周期性心跳, 暴露所有记忆操作
    """

    def __init__(
        self,
        service_id: str = "tianji-memory",
        host: str = "0.0.0.0",
        port: int = 8700,
        event_bus=None,
        registry=None,
        resilience=None,
    ):
        self.service_id = service_id
        self.host = host
        self.port = port
        self._event_bus = event_bus
        self._registry = registry
        self._resilience = resilience
        self._server: Optional[grpc.Server] = None
        self._running = False

        if not GRPC_AVAILABLE:
            logger.warning("grpcio not installed — gRPC server disabled")
        if not PROTO_AVAILABLE:
            logger.warning("proto stubs not generated — run: python -m grpc_tools.protoc ...")

    def start(self):
        if not GRPC_AVAILABLE or not PROTO_AVAILABLE:
            logger.warning("gRPC prerequisites missing — server not started")
            return

        self._server = grpc.server(threading.ThreadPoolExecutor(max_workers=10))

        lingjing_pb2_grpc.add_MemoryServiceServicer_to_server(
            MemoryServiceServicer(self._event_bus, self._resilience), self._server
        )
        lingjing_pb2_grpc.add_LingjingRegistryServicer_to_server(
            RegistryServiceServicer(self._registry, self._event_bus), self._server
        )
        lingjing_pb2_grpc.add_LingjingEventBusServicer_to_server(
            EventBusServiceServicer(self._event_bus), self._server
        )
        lingjing_pb2_grpc.add_AgentServiceServicer_to_server(
            AgentServiceServicer(self._resilience), self._server
        )

        SERVICE_NAMES = (
            lingjing_pb2.DESCRIPTOR.services_by_name["MemoryService"].full_name,
            lingjing_pb2.DESCRIPTOR.services_by_name["LingjingRegistry"].full_name,
            lingjing_pb2.DESCRIPTOR.services_by_name["LingjingEventBus"].full_name,
            lingjing_pb2.DESCRIPTOR.services_by_name["AgentService"].full_name,
            reflection.SERVICE_NAME,
        )
        reflection.enable_server_reflection(SERVICE_NAMES, self._server)

        self._server.add_insecure_port(f"{self.host}:{self.port}")
        self._server.start()
        self._running = True

        if self._registry:
            self._registry.register(
                self.service_id,
                name="天机记忆引擎",
                host=self.host,
                port=self.port,
                layer="L1",
                capabilities=["memory", "knowledge", "search", "classify"],
                health_endpoint=f"/health/memory",
                version="8.2-grpc",
            )

        if self._event_bus:
            self._event_bus.publish("grpc_server_started", "grpc_server", {
                "service_id": self.service_id,
                "host": self.host,
                "port": self.port,
            })

        logger.info(f"gRPC server started: {self.host}:{self.port} ({self.service_id})")

        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def stop(self):
        self._running = False
        if self._server:
            self._server.stop(grace=5)

        if self._registry:
            self._registry.deregister(self.service_id)

        if self._event_bus:
            self._event_bus.publish("grpc_server_stopped", "grpc_server", {
                "service_id": self.service_id,
            })

        logger.info(f"gRPC server stopped: {self.service_id}")

    def _heartbeat_loop(self):
        while self._running:
            time.sleep(15)
            if self._registry:
                self._registry.heartbeat(self.service_id)

    def get_stats(self):
        return {
            "service_id": self.service_id,
            "host": self.host,
            "port": self.port,
            "running": self._running,
            "grpc_available": GRPC_AVAILABLE,
            "proto_available": PROTO_AVAILABLE,
        }


class MemoryServiceServicer(lingjing_pb2_grpc.MemoryServiceServicer if PROTO_AVAILABLE else object):

    def __init__(self, event_bus=None, resilience=None):
        self._event_bus = event_bus
        self._resilience = resilience

    def _check_resilience(self):
        if self._resilience and not self._resilience.request("tianji-memory"):
            return False
        return True

    def Remember(self, request, context):
        if not self._check_resilience():
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            return lingjing_pb2.RememberResponse()
        try:
            result = _call_memory_api("POST", "/api/memory/", {
                "content": request.content,
                "layer": request.layer or "working",
                "tags": list(request.tags),
                "priority": request.priority or "medium",
            })
            if self._resilience:
                self._resilience.success("tianji-memory")
            if result:
                return lingjing_pb2.RememberResponse(
                    memory_id=result.get("memory_id", ""),
                    layer=result.get("layer", ""),
                    gate_verdict=result.get("gate_verdict", ""),
                    system=result.get("system", "TIANJI"),
                )
        except Exception:
            if self._resilience:
                self._resilience.failure("tianji-memory")
        return lingjing_pb2.RememberResponse()

    def Recall(self, request, context):
        if not self._check_resilience():
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            return lingjing_pb2.RecallResponse()
        try:
            result = _call_memory_api("GET", f"/api/memory/search?q={request.query}&limit={request.limit}")
            if self._resilience:
                self._resilience.success("tianji-memory")
            items = result.get("items", []) if result else []
            return lingjing_pb2.RecallResponse(
                items=[lingjing_pb2.MemoryItem(
                    memory_id=it.get("id", ""),
                    content=it.get("content", "")[:500],
                    layer=it.get("layer", "working"),
                    tags=it.get("tags", []),
                    score=it.get("score", 0.0),
                ) for it in items],
                total=len(items),
            )
        except Exception:
            if self._resilience:
                self._resilience.failure("tianji-memory")
        return lingjing_pb2.RecallResponse()

    def Forget(self, request, context):
        try:
            result = _call_memory_api("DELETE", f"/api/memory/{request.memory_id}")
            return lingjing_pb2.ForgetResponse(
                memory_id=request.memory_id,
                status="forgotten" if result else "not_found",
            )
        except Exception:
            return lingjing_pb2.ForgetResponse(memory_id=request.memory_id, status="error")

    def Stats(self, request, context):
        try:
            result = _call_memory_api("GET", "/api/memory/stats")
            if not result:
                return lingjing_pb2.StatsResponse(status="unavailable")
            layers = result.get("layers", {})
            return lingjing_pb2.StatsResponse(
                status="healthy",
                total_entries=result.get("total_entries", 0),
                layers=[lingjing_pb2.LayerStats(
                    layer=name,
                    entry_count=info.get("entry_count", 0),
                    size_bytes=info.get("size_bytes", 0),
                    usage_ratio=info.get("usage_ratio", 0.0),
                ) for name, info in layers.items()],
                uptime_seconds=result.get("uptime_seconds", 0.0),
            )
        except Exception:
            return lingjing_pb2.StatsResponse(status="error")

    def Classify(self, request, context):
        try:
            result = _call_memory_api("POST", "/api/llm/classify", {
                "content": request.content,
            })
            return lingjing_pb2.ClassifyResponse(
                content=result.get("content", request.content) if result else request.content,
                recommended_layer=result.get("recommended_layer", "working") if result else "working",
                confidence=result.get("confidence", 0.5) if result else 0.5,
            )
        except Exception:
            return lingjing_pb2.ClassifyResponse()

    def ExtractKnowledge(self, request, context):
        try:
            result = _call_memory_api("POST", "/api/llm/extract-knowledge", {
                "content": request.content,
            })
            triples = result.get("triples", []) if result else []
            return lingjing_pb2.ExtractKnowledgeResponse(
                triples=[lingjing_pb2.KnowledgeTriple(
                    subject=t.get("subject", ""),
                    relation=t.get("relation", ""),
                    object=t.get("object", ""),
                    confidence=t.get("confidence", 0.5),
                ) for t in triples],
                total=len(triples),
            )
        except Exception:
            return lingjing_pb2.ExtractKnowledgeResponse()

    def Summarize(self, request, context):
        try:
            result = _call_memory_api("POST", "/api/llm/summarize", {
                "content": request.content,
                "max_length": request.max_length or 200,
            })
            return lingjing_pb2.SummarizeResponse(
                summary=result.get("summary", "") if result else "",
                original_length=len(request.content),
                summary_length=len(result.get("summary", "")) if result else 0,
            )
        except Exception:
            return lingjing_pb2.SummarizeResponse()

    def SemanticSearch(self, request, context):
        try:
            result = _call_memory_api("POST", "/api/search/semantic", {
                "query": request.query,
                "limit": request.limit or 10,
                "threshold": request.threshold or 0.1,
            })
            results = result.get("results", []) if result else []
            return lingjing_pb2.SemanticSearchResponse(
                results=[lingjing_pb2.SearchResult(
                    memory_id=r.get("memory_id", ""),
                    content=r.get("content", "")[:500],
                    similarity=r.get("similarity", 0.0),
                    layer=r.get("layer", "semantic"),
                ) for r in results],
                total=len(results),
            )
        except Exception:
            return lingjing_pb2.SemanticSearchResponse()

    def Health(self, request, context):
        try:
            result = _call_memory_api("GET", "/api/health")
            return lingjing_pb2.HealthResponse(
                status=result.get("status", "unknown") if result else "unavailable",
                version=result.get("version", "8.2") if result else "8.2",
                engine_ready=result.get("engine_ready", False) if result else False,
                uptime_seconds=result.get("uptime_seconds", 0.0) if result else 0.0,
            )
        except Exception:
            return lingjing_pb2.HealthResponse(status="error", version="8.2")


class RegistryServiceServicer(lingjing_pb2_grpc.LingjingRegistryServicer if PROTO_AVAILABLE else object):

    def __init__(self, registry=None, event_bus=None):
        self._registry = registry
        self._event_bus = event_bus

    def Register(self, request, context):
        try:
            if self._registry:
                self._registry.register(
                    request.service_id,
                    name=request.name,
                    host=request.host,
                    port=request.port,
                    layer=request.layer,
                    capabilities=list(request.capabilities),
                    health_endpoint=request.health_endpoint,
                    version=request.version,
                )
            return lingjing_pb2.RegisterResponse(
                service_id=request.service_id,
                registered=True,
                message=f"Service {request.name} registered",
            )
        except Exception as e:
            return lingjing_pb2.RegisterResponse(service_id=request.service_id, registered=False, message=str(e))

    def Heartbeat(self, request, context):
        ack = bool(self._registry and self._registry.heartbeat(request.service_id))
        return lingjing_pb2.HeartbeatResponse(service_id=request.service_id, acknowledged=ack)

    def Discover(self, request, context):
        services = []
        if self._registry:
            records = self._registry.discover(
                layer=request.layer or None,
                capability=request.capability or None,
            )
            services = [lingjing_pb2.ServiceInfo(
                service_id=r.service_id,
                name=r.name,
                host=r.host,
                port=r.port,
                layer=r.layer,
                capabilities=r.capabilities,
                status=r.status.value,
                is_alive=r.is_alive(),
            ) for r in records]
        return lingjing_pb2.DiscoverResponse(services=services, total=len(services))

    def Deregister(self, request, context):
        if self._registry:
            self._registry.deregister(request.service_id)
        return lingjing_pb2.DeregisterResponse(service_id=request.service_id, deregistered=True)


class EventBusServiceServicer(lingjing_pb2_grpc.LingjingEventBusServicer if PROTO_AVAILABLE else object):

    def __init__(self, event_bus=None):
        self._event_bus = event_bus

    def Publish(self, request, context):
        event_id = ""
        published = False
        if self._event_bus:
            payload = json.loads(request.payload_json) if request.payload_json else {}
            event_id = self._event_bus.publish(request.event_type, request.source, payload)
            published = bool(event_id)
        return lingjing_pb2.PublishResponse(event_id=event_id, published=published)

    def Subscribe(self, request_iterator, context):
        for req in request_iterator:
            if self._event_bus:
                queue = []
                def _on_event(evt):
                    queue.append(evt)
                sub_id = f"grpc_{req.subscriber_id}"
                self._event_bus.subscribe(sub_id, req.event_type, _on_event)
                import time as _t
                start = _t.time()
                while _t.time() - start < 300:
                    for evt in list(queue):
                        queue.remove(evt)
                        yield lingjing_pb2.BusEvent(
                            event_id=evt.event_id,
                            event_type=evt.event_type,
                            source=evt.source,
                            payload_json=json.dumps(evt.payload, ensure_ascii=False),
                            timestamp=evt.timestamp,
                        )
                    _t.sleep(1)
                self._event_bus.unsubscribe(sub_id, req.event_type)


class AgentServiceServicer(lingjing_pb2_grpc.AgentServiceServicer if PROTO_AVAILABLE else object):

    def __init__(self, resilience=None):
        self._resilience = resilience
        self._tasks = {}
        self._agents = {
            "tiewei": ("铁卫", "L0", ["quality-gate", "test"], "/health/quality-gate"),
            "yiku": ("忆库", "L1", ["memory", "search", "knowledge"], "/health/memory"),
            "dongcha": ("洞察", "L1", ["context", "intent"], "/health/context"),
            "luling": ("律令", "L1", ["rules", "governance"], "/health/rules"),
            "lingxi": ("灵犀", "L1", ["session", "dialogue"], "/health/session"),
            "tianshu": ("天枢", "L2", ["orchestrator", "dispatch"], "/health/orchestrator"),
            "wenzong": ("文宗", "L2", ["editor", "content"], "/health/editor"),
            "jingwei": ("经纬", "L2", ["architecture", "planning"], "/health/architect"),
            "miaobi": ("妙笔", "L2", ["creator", "generation"], "/health/creator"),
            "mingjing": ("明镜", "L2", ["review", "audit"], "/health/reviewer"),
            "tiansuan": ("天算", "L2", ["analysis", "statistics"], "/health/analyst"),
            "kuangshi": ("矿师", "L2", ["corpus", "data-mining"], "/health/corpus"),
            "baiqiao": ("百巧", "L3", ["skills", "tools"], "/health/skills"),
            "shiguan": ("史官", "L3", ["history", "archive"], "/health/history"),
            "jinshu": ("锦书", "L3", ["export", "format"], "/health/export"),
            "qianli": ("千里", "L4", ["monitor", "observability"], "/health/monitor"),
            "gongzao": ("工造", "L4", ["devops", "build"], "/health/devops"),
            "zhenshan": ("镇山", "L4", ["security", "shield"], "/health/security"),
            "zhuiguang": ("追光", "L4", ["performance", "profiling"], "/health/performance"),
            "tianji": ("天机", "L2", ["system", "core"], "/health/tianji"),
            "lianli": ("连理", "L2", ["graph", "knowledge"], "/health/graph"),
            "huasheng": ("化生", "L3", ["evolution", "self-improve"], "/health/evolver"),
            "wanxiang": ("万象", "L1", ["multimodal", "perception"], "/health/multimodal"),
        }

    def Dispatch(self, request, context):
        if self._resilience and not self._resilience.request("agent-dispatch"):
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            return lingjing_pb2.DispatchResponse()
        task_id = f"task_{int(time.time()*1000)}_{hash(request.task_type) & 0xFFFF:04x}"
        self._tasks[task_id] = {
            "task_type": request.task_type,
            "task_data": request.task_data_json,
            "priority": request.priority,
            "status": "dispatched",
            "agent_id": "tianshu",
            "timestamp": time.time(),
        }
        if self._resilience:
            self._resilience.success("agent-dispatch")
        return lingjing_pb2.DispatchResponse(task_id=task_id, agent_id="tianshu", status="dispatched")

    def GetStatus(self, request, context):
        agent = self._agents.get(request.agent_id, ("Unknown", "L0", [], ""))
        return lingjing_pb2.AgentStatusResponse(
            agent_id=request.agent_id,
            name=agent[0],
            status="online",
            uptime_seconds=0.0,
            tasks_handled=0,
        )

    def ListCapabilities(self, request, context):
        return lingjing_pb2.ListCapabilitiesResponse(
            agents=[lingjing_pb2.AgentCapability(
                agent_id=aid,
                name=info[0],
                layer=info[1],
                capabilities=info[2],
                health_endpoint=info[3],
            ) for aid, info in self._agents.items()],
            total=len(self._agents),
        )


def _call_memory_api(method: str, path: str, data: dict = None) -> dict:
    try:
        import urllib.request
        import urllib.error
        url = f"http://127.0.0.1:8771{path}"
        if data:
            req = urllib.request.Request(url, method=method,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


_SEED_INSTANCE: Optional[TianjiGRPCServer] = None


def get_grpc_server() -> TianjiGRPCServer:
    global _SEED_INSTANCE
    if _SEED_INSTANCE is None:
        _SEED_INSTANCE = TianjiGRPCServer()
    return _SEED_INSTANCE
