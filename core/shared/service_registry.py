r"""
天机服务注册与发现 (Service Registry) v1.0
====================================================
灵境分布式就绪 — 服务注册/心跳/发现 核心

核心特性:
  1. 服务注册: 自动注册+元数据+端口分配
  2. 心跳维持: 周期性TTL心跳，超时自动降级
  3. 健康检查: HTTP端点主动探测
  4. 服务发现: 按capability/layer查询服务清单
  5. 事件通知: 服务上/下线 → EvolutionBus广播

与灵境对接:
  灵境Phase 3: ServiceRegistry → Consul/etcd服务发现
  灵境Phase 4: 跨节点服务路由

架构位置: 天机/core/service_registry.py
依赖: core/evolution_bus (事件广播)

灵境道谱溯源: D6-7【服务散落煞】· 道六·注册体道 · 四地煞之序之术
"""

import time
import json
import logging
import threading
import socket
import urllib.request
from typing import Any, Optional, Dict, List, Callable
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class ServiceRecord:
    service_id: str
    name: str
    host: str
    port: int
    layer: str = "L0"
    capabilities: List[str] = field(default_factory=list)
    health_endpoint: str = ""
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: ServiceStatus = ServiceStatus.ONLINE
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    heartbeat_ttl: float = 30.0
    failed_checks: int = 0

    def is_alive(self) -> bool:
        return (time.time() - self.last_heartbeat) < self.heartbeat_ttl

    def to_dict(self) -> dict:
        return {
            "service_id": self.service_id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "layer": self.layer,
            "capabilities": self.capabilities,
            "health_endpoint": self.health_endpoint,
            "version": self.version,
            "status": self.status.value,
            "uptime_seconds": round(time.time() - self.registered_at, 1),
            "last_heartbeat_ago": round(time.time() - self.last_heartbeat, 1),
            "is_alive": self.is_alive(),
        }


class ServiceRegistry:
    """
    天机服务注册中心 v1.0

    用法:
      registry = ServiceRegistry()
      registry.register("tiewei", host="127.0.0.1", port=8810, layer="L0")
      registry.heartbeat("tiewei")
      services = registry.discover(layer="L0")
    """

    def __init__(
        self,
        db_path: str = "data/service_registry.db",
        heartbeat_interval: float = 15.0,
        heartbeat_ttl: float = 45.0,
        health_check_interval: float = 30.0,
        event_bus=None,
    ):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_ttl = heartbeat_ttl
        self._health_check_interval = health_check_interval

        self._services: Dict[str, ServiceRecord] = {}
        self._lock = threading.RLock()
        self._running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._health_check_thread: Optional[threading.Thread] = None
        self._event_bus = event_bus

        self._stats = {
            "registered": 0,
            "heartbeats_received": 0,
            "services_up": 0,
            "services_down": 0,
            "health_checks_passed": 0,
            "health_checks_failed": 0,
            "started_at": time.time(),
        }

        self._init_db()
        logger.info("ServiceRegistry v1.0 initialized")

    def _init_db(self):
        try:
            import sqlite3
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS service_registry (
                    service_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    layer TEXT DEFAULT 'L0',
                    capabilities TEXT DEFAULT '[]',
                    health_endpoint TEXT DEFAULT '',
                    version TEXT DEFAULT '1.0.0',
                    status TEXT DEFAULT 'online',
                    registered_at REAL,
                    last_heartbeat REAL
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"ServiceRegistry DB init: {e}")

    def _persist_service(self, record: ServiceRecord):
        try:
            import sqlite3
            conn = sqlite3.connect(str(self._db_path))
            conn.execute(
                """INSERT OR REPLACE INTO service_registry
                   (service_id, name, host, port, layer, capabilities, health_endpoint, version, status, registered_at, last_heartbeat)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record.service_id, record.name, record.host, record.port,
                    record.layer, json.dumps(record.capabilities, ensure_ascii=False),
                    record.health_endpoint, record.version, record.status.value,
                    record.registered_at, record.last_heartbeat
                )
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def register(
        self,
        service_id: str,
        name: str = "",
        host: str = "127.0.0.1",
        port: int = 0,
        layer: str = "L0",
        capabilities: List[str] = None,
        health_endpoint: str = "",
        version: str = "1.0.0",
        metadata: Dict[str, Any] = None,
    ) -> ServiceRecord:
        """
        注册服务到注册中心

        Args:
            service_id: 服务唯一ID (agent_id)
            name: 服务名称
            host: 服务地址
            port: 服务端口
            layer: 服务层级 L0-L4
            capabilities: 能力标签列表
            health_endpoint: 健康检查端点 (如 /health/memory)
            version: 服务版本
            metadata: 额外元数据
        """
        if port == 0:
            port = self._assign_port(service_id)

        record = ServiceRecord(
            service_id=service_id,
            name=name or service_id,
            host=host,
            port=port,
            layer=layer,
            capabilities=capabilities or [],
            health_endpoint=health_endpoint,
            version=version,
            metadata=metadata or {},
        )

        is_new = service_id not in self._services
        with self._lock:
            old_status = self._services[service_id].status if service_id in self._services else None
            self._services[service_id] = record
            if is_new:
                self._stats["registered"] += 1

        self._persist_service(record)

        if self._event_bus:
            event_type = "service_registered" if is_new else "service_reconnected"
            try:
                self._event_bus.publish(event_type, "service_registry", {
                    "service_id": service_id,
                    "name": record.name,
                    "host": host,
                    "port": port,
                    "layer": layer,
                    "previous_status": old_status.value if old_status else None,
                })
            except Exception:
                pass

        logger.info(f"Service registered: {name} ({service_id}) {host}:{port} [{layer}]")
        return record

    def heartbeat(self, service_id: str) -> bool:
        """
        服务心跳

        Returns:
            True if service found and heartbeat recorded
        """
        with self._lock:
            if service_id not in self._services:
                logger.warning(f"Heartbeat from unknown service: {service_id}")
                return False
            record = self._services[service_id]
            previous_status = record.status
            record.last_heartbeat = time.time()

            if record.status == ServiceStatus.OFFLINE:
                record.status = ServiceStatus.ONLINE
                record.failed_checks = 0
                self._stats["services_up"] += 1
                if self._event_bus:
                    try:
                        self._event_bus.publish("service_online", "service_registry", {
                            "service_id": service_id,
                            "name": record.name,
                            "previous_status": previous_status.value,
                        })
                    except Exception:
                        pass

            self._stats["heartbeats_received"] += 1

        self._persist_service(record)
        return True

    def deregister(self, service_id: str):
        with self._lock:
            if service_id in self._services:
                record = self._services.pop(service_id)
                record.status = ServiceStatus.OFFLINE
                logger.info(f"Service deregistered: {record.name} ({service_id})")
                if self._event_bus:
                    try:
                        self._event_bus.publish("service_offline", "service_registry", {
                            "service_id": service_id,
                            "name": record.name,
                        })
                    except Exception:
                        pass

    def discover(
        self,
        layer: str = None,
        capability: str = None,
        include_offline: bool = False,
    ) -> List[ServiceRecord]:
        """服务发现"""
        results = []
        with self._lock:
            for record in self._services.values():
                if not include_offline and record.status == ServiceStatus.OFFLINE:
                    continue
                if layer and record.layer != layer:
                    continue
                if capability and capability not in record.capabilities:
                    continue
                results.append(record)
        return results

    def get_service(self, service_id: str) -> Optional[ServiceRecord]:
        with self._lock:
            return self._services.get(service_id)

    def health_check(self, service_id: str = None) -> Dict[str, Any]:
        """主动健康检查 (HTTP端点探测)"""
        services_to_check = [self._services[service_id]] if service_id else list(self._services.values())
        results = {}

        for record in services_to_check:
            check_result = self._probe_service(record)
            results[record.service_id] = check_result

            if check_result["healthy"]:
                self._stats["health_checks_passed"] += 1
                record.failed_checks = 0
            else:
                self._stats["health_checks_failed"] += 1
                record.failed_checks += 1
                if record.failed_checks >= 3:
                    previous = record.status
                    record.status = ServiceStatus.DEGRADED
                    record.last_heartbeat = time.time()
                    if previous == ServiceStatus.ONLINE:
                        self._stats["services_down"] += 1
                        if self._event_bus:
                            try:
                                self._event_bus.publish("service_degraded", "service_registry", {
                                    "service_id": record.service_id,
                                    "failed_checks": record.failed_checks,
                                })
                            except Exception:
                                pass

        return results

    def _probe_service(self, record: ServiceRecord) -> Dict[str, Any]:
        if not record.health_endpoint:
            alive = record.is_alive()
            return {"healthy": alive, "method": "heartbeat_ttl", "detail": "alive_by_ttl" if alive else "ttl_expired"}

        try:
            url = f"http://{record.host}:{record.port}{record.health_endpoint}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"healthy": True, "method": "http_probe", "status_code": resp.status, "response": data}
        except Exception as e:
            return {"healthy": False, "method": "http_probe", "error": str(e)[:200]}

    def _heartbeat_loop(self):
        """后台心跳维护线程"""
        while self._running:
            time.sleep(self._heartbeat_interval)
            with self._lock:
                now = time.time()
                for record in list(self._services.values()):
                    if record.status != ServiceStatus.OFFLINE and not record.is_alive():
                        previous = record.status
                        record.status = ServiceStatus.OFFLINE
                        self._stats["services_down"] += 1
                        logger.warning(f"Service heart-expired: {record.name} ({record.service_id})")
                        if self._event_bus:
                            try:
                                self._event_bus.publish("service_heart_expired", "service_registry", {
                                    "service_id": record.service_id,
                                    "name": record.name,
                                    "previous_status": previous.value,
                                })
                            except Exception:
                                pass

    def _health_check_loop(self):
        """后台健康检查线程"""
        while self._running:
            time.sleep(self._health_check_interval)
            self.health_check()

    def start(self):
        self._running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        self._health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._health_check_thread.start()
        logger.info("ServiceRegistry background loops started")

    def stop(self):
        self._running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)
        logger.info("ServiceRegistry stopped")

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            services_detail = {
                sid: {
                    "name": r.name,
                    "status": r.status.value,
                    "alive": r.is_alive(),
                    "heartbeat_ago": round(time.time() - r.last_heartbeat, 1),
                    "uptime": round(time.time() - r.registered_at, 1),
                    "failed_checks": r.failed_checks,
                }
                for sid, r in self._services.items()
            }
            return {
                **self._stats,
                "total_services": len(self._services),
                "online_count": sum(1 for r in self._services.values() if r.status == ServiceStatus.ONLINE),
                "degraded_count": sum(1 for r in self._services.values() if r.status == ServiceStatus.DEGRADED),
                "offline_count": sum(1 for r in self._services.values() if r.status == ServiceStatus.OFFLINE),
                "services": services_detail,
                "uptime_seconds": round(time.time() - self._stats["started_at"], 1),
            }

    def _assign_port(self, service_id: str) -> int:
        base_ports = {"L0": 8810, "L1": 8820, "L2": 8800, "L3": 8830, "L4": 8840}
        base = base_ports.get(self._services.get(service_id, ServiceRecord(service_id=service_id, name="", host="", port=0)).layer, 8800)
        used = {r.port for r in self._services.values()}
        for offset in range(50):
            candidate = base + offset
            if candidate not in used:
                return candidate
        return base + len(used)


_GLOBAL_REGISTRY: Optional[ServiceRegistry] = None
_REGISTRY_LOCK = threading.Lock()


def get_service_registry() -> ServiceRegistry:
    global _GLOBAL_REGISTRY
    with _REGISTRY_LOCK:
        if _GLOBAL_REGISTRY is None:
            _GLOBAL_REGISTRY = ServiceRegistry()
        return _GLOBAL_REGISTRY
