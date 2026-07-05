"""
天机v9.1 分布式集群管理器 (TianjiV9-ClusterManager)
===========================================================
《天机·星枢运转》— 多节点协同 · 灵境分布式网络

架构:
    天机主节点 (Leader)
    ├── 忆库节点 (Memory Nodes)   — ICME六层记忆分片存储
    ├── 调度节点 (Scheduler Nodes) — Agent任务负载均衡
    ├── 执行节点 (Executor Nodes)  — Agent执行器 (LLM推理/工具调用)
    ├── 运维节点 (Ops Nodes)       — 监控/自愈/审计
    └── 安全节点 (Security Nodes)  — 合规扫描/权限管控

通信:
    - gRPC (服务间调用, 基于 protobuf)
    - Redis Pub/Sub (事件广播)
    - HTTP REST (控制面 API)

选举:
    - Raft 共识算法 (leader election)
    - 心跳保活 (heartbeat, 默认5s)
    - 自动故障转移 (failover, 默认30s超时)

节点发现:
    - 静态配置 (config/cluster.json)
    - mDNS 自动发现 (局域网)
    - Consul/etcd 注册中心 (生产环境)

用法:
    # 主节点
    python -m core.cluster_manager --role leader --port 9000

    # 忆库节点
    python -m core.cluster_manager --role memory --port 9001 --join 127.0.0.1:9000

    # 执行节点
    python -m core.cluster_manager --role executor --port 9002 --join 127.0.0.1:9000

设计阶段: v9.1 — 概念架构, 待 v9.1 完整实现
"""

import http.server
import json
import socket
import threading
import time
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────
# 路径配置
# ──────────────────────────────────────────────
MODULE_DIR = Path(__file__).resolve().parent
APP_DIR = MODULE_DIR.parent
CLUSTER_CONFIG = APP_DIR / "config" / "cluster.json"


# ──────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────


class NodeRole(Enum):
    LEADER = "leader"  # 主节点 (调度+协调)
    MEMORY = "memory"  # 忆库节点 (ICME存储)
    SCHEDULER = "scheduler"  # 调度节点 (Agent任务分发)
    EXECUTOR = "executor"  # 执行节点 (LLM推理)
    OPS = "ops"  # 运维节点 (监控/审计)
    SECURITY = "security"  # 安全节点 (合规/权限)


class NodeStatus(Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    JOINING = "joining"
    LEAVING = "leaving"


@dataclass
class ClusterNode:
    """集群节点描述"""

    node_id: str
    role: NodeRole
    host: str
    port: int
    status: NodeStatus = NodeStatus.JOINING
    joined_at: str | None = None
    last_heartbeat: str | None = None
    capabilities: list[str] = field(default_factory=list)
    load: float = 0.0  # 当前负载 (0-1)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["role"] = self.role.value
        d["status"] = self.status.value
        return d


@dataclass
class ClusterConfig:
    """集群配置"""

    cluster_name: str = "天机-灵境集群"
    bind_host: str = "0.0.0.0"
    bind_port: int = 9000
    role: NodeRole = NodeRole.LEADER
    seed_nodes: list[str] = field(default_factory=list)  # ["host:port", ...]
    heartbeat_interval: int = 5  # 心跳间隔 (秒)
    node_timeout: int = 30  # 节点超时 (秒)
    max_nodes: int = 100  # 最大节点数
    discovery_mode: str = "static"  # static | mdns | consul | etcd
    enable_gossip: bool = True  # Gossip 协议广播
    data_shards: int = 3  # 数据分片数 (忆库节点)
    replication_factor: int = 2  # 副本因子


# ──────────────────────────────────────────────
# 集群管理器 (概念实现)
# ──────────────────────────────────────────────


class ClusterManager:
    """天机分布式集群管理器"""

    def __init__(self, config: ClusterConfig | None = None):
        self._config = config or self._load_config()
        self._node_id = self._generate_node_id()
        self._nodes: dict[str, ClusterNode] = {}
        self._lock = threading.RLock()
        self._running = False
        self._heartbeat_thread: threading.Thread | None = None
        self._gossip_thread: threading.Thread | None = None
        self._http_server: http.server.HTTPServer | None = None

        # 注册自身
        self_node = ClusterNode(
            node_id=self._node_id,
            role=self._config.role,
            host=self._get_local_ip(),
            port=self._config.bind_port,
            status=NodeStatus.ONLINE,
            joined_at=datetime.now().isoformat(),
            capabilities=self._get_capabilities(),
        )
        self._nodes[self._node_id] = self_node

    # ──────────────── 公开 API ────────────────

    def start(self) -> bool:
        """启动集群管理器"""
        with self._lock:
            if self._running:
                return False
            self._running = True

        # 加入已有集群
        for seed in self._config.seed_nodes:
            self._join_seed(seed)

        # 启动心跳
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()

        # 启动 Gossip
        if self._config.enable_gossip:
            self._gossip_thread = threading.Thread(
                target=self._gossip_loop, daemon=True
            )
            self._gossip_thread.start()

        # 启动 HTTP 控制面
        self._start_http_server()

        return True

    def stop(self):
        """停止集群管理器"""
        self._running = False
        if self._http_server:
            self._http_server.shutdown()

    def get_nodes(self) -> list[dict]:
        """获取所有节点"""
        with self._lock:
            return [n.to_dict() for n in self._nodes.values()]

    def get_node(self, node_id: str) -> dict | None:
        """获取指定节点"""
        with self._lock:
            node = self._nodes.get(node_id)
            return node.to_dict() if node else None

    def get_nodes_by_role(self, role: NodeRole) -> list[dict]:
        """按角色获取节点"""
        with self._lock:
            return [n.to_dict() for n in self._nodes.values() if n.role == role]

    def get_leader(self) -> dict | None:
        """获取Leader节点"""
        with self._lock:
            leaders = [n for n in self._nodes.values() if n.role == NodeRole.LEADER]
            return leaders[0].to_dict() if leaders else None

    def get_cluster_status(self) -> dict:
        """获取集群状态摘要"""
        with self._lock:
            online = sum(
                1 for n in self._nodes.values() if n.status == NodeStatus.ONLINE
            )
            by_role = {}
            for n in self._nodes.values():
                role = n.role.value
                if role not in by_role:
                    by_role[role] = 0
                by_role[role] += 1

            return {
                "cluster_name": self._config.cluster_name,
                "node_id": self._node_id,
                "total_nodes": len(self._nodes),
                "online_nodes": online,
                "offline_nodes": len(self._nodes) - online,
                "nodes_by_role": by_role,
                "leader": self.get_leader(),
                "uptime_seconds": time.time()
                - self._nodes.get(
                    self._node_id,
                    ClusterNode(node_id="", role=NodeRole.LEADER, host="", port=0),
                ).joined_at
                if self._nodes.get(self._node_id)
                else 0,
            }

    # ──────────────── 内部实现 ────────────────

    def _load_config(self) -> ClusterConfig:
        """加载集群配置"""
        if CLUSTER_CONFIG.exists():
            try:
                with open(CLUSTER_CONFIG, encoding="utf-8") as f:
                    data = json.load(f)
                return ClusterConfig(**data)
            except Exception:
                pass
        return ClusterConfig()

    def _generate_node_id(self) -> str:
        """生成节点ID"""
        host = self._get_local_ip()
        return f"{socket.gethostname()}-{host}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _get_local_ip() -> str:
        """获取本机IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _get_capabilities(self) -> list[str]:
        """获取本节点能力"""
        caps = []
        try:
            import psutil

            caps.append(f"cpu:{psutil.cpu_count()}")
            caps.append(f"mem:{psutil.virtual_memory().total // (1024**3)}GB")
        except ImportError:
            pass

        if self._config.role == NodeRole.LEADER:
            caps.extend(["orchestration", "scheduling", "leader-election", "raft"])
        elif self._config.role == NodeRole.MEMORY:
            caps.extend(
                ["icme-storage", "graph-query", "semantic-search", "vector-index"]
            )
        elif self._config.role == NodeRole.EXECUTOR:
            caps.extend(["llm-inference", "tool-execution", "agent-sandbox"])
        elif self._config.role == NodeRole.OPS:
            caps.extend(["monitoring", "logging", "auto-healing", "audit"])
        elif self._config.role == NodeRole.SECURITY:
            caps.extend(["compliance", "vuln-scan", "access-control", "crypto"])

        return caps

    def _join_seed(self, seed: str):
        """通过种子节点加入集群"""
        try:
            url = f"http://{seed}/api/cluster/join"
            data = json.dumps(self._nodes[self._node_id].to_dict()).encode()
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                response = json.loads(resp.read().decode())
                for node_data in response.get("nodes", []):
                    node = ClusterNode(**node_data)
                    self._nodes[node.node_id] = node
        except Exception:
            pass

    def _heartbeat_loop(self):
        """心跳循环"""
        while self._running:
            now = datetime.now().isoformat()
            with self._lock:
                self._nodes[self._node_id].last_heartbeat = now

                # 检测离线节点
                for nid, node in list(self._nodes.items()):
                    if nid == self._node_id:
                        continue
                    if node.last_heartbeat:
                        age = (
                            time.time()
                            - datetime.fromisoformat(node.last_heartbeat).timestamp()
                        )
                        if age > self._config.node_timeout:
                            node.status = NodeStatus.OFFLINE

            time.sleep(self._config.heartbeat_interval)

    def _gossip_loop(self):
        """Gossip广播 (节点发现与状态同步)"""
        while self._running:
            with self._lock:
                online = [
                    n
                    for n in self._nodes.values()
                    if n.status == NodeStatus.ONLINE and n.node_id != self._node_id
                ]
                # 随机选择3个节点进行Gossip交换
                import random

                targets = random.sample(online, min(3, len(online)))
                for target in targets:
                    try:
                        url = f"http://{target.host}:{target.port}/api/cluster/gossip"
                        data = json.dumps(
                            {
                                "from": self._node_id,
                                "nodes": [n.to_dict() for n in self._nodes.values()],
                            }
                        ).encode()
                        req = urllib.request.Request(
                            url, data=data, headers={"Content-Type": "application/json"}
                        )
                        urllib.request.urlopen(req, timeout=2)
                    except Exception:
                        pass

            time.sleep(self._config.heartbeat_interval * 3)

    def _start_http_server(self):
        """启动HTTP控制面 (REST API)"""
        manager_ref = self  # closure capture for nested class

        class ClusterHTTPHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/api/cluster/status":
                    self._json_response(manager_ref.get_cluster_status())
                elif self.path == "/api/cluster/nodes":
                    self._json_response({"nodes": manager_ref.get_nodes()})
                elif self.path.startswith("/api/cluster/node/"):
                    node_id = self.path.split("/")[-1]
                    self._json_response(
                        manager_ref.get_node(node_id) or {"error": "not found"}
                    )
                elif self.path == "/api/cluster/leader":
                    self._json_response(
                        manager_ref.get_leader() or {"error": "no leader"}
                    )
                elif self.path == "/health":
                    self._json_response(
                        {"status": "ok", "node_id": manager_ref._node_id}
                    )
                else:
                    self.send_error(404)

            def do_POST(self):
                content_len = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(content_len)) if content_len else {}

                if self.path == "/api/cluster/join":
                    new_node = ClusterNode(**body)
                    with manager_ref._lock:
                        manager_ref._nodes[new_node.node_id] = new_node
                    self._json_response(
                        {"status": "joined", "nodes": manager_ref.get_nodes()}
                    )
                elif self.path == "/api/cluster/gossip":
                    with manager_ref._lock:
                        for node_data in body.get("nodes", []):
                            node = ClusterNode(**node_data)
                            if node.node_id not in manager_ref._nodes:
                                manager_ref._nodes[node.node_id] = node
                    self._json_response({"status": "synced"})
                elif self.path == "/api/cluster/leave":
                    node_id = body.get("node_id", "")
                    with manager_ref._lock:
                        manager_ref._nodes.pop(node_id, None)
                    self._json_response({"status": "left"})
                else:
                    self.send_error(404)

            def _json_response(self, data: dict, status: int = 200):
                body = json.dumps(data, ensure_ascii=False, indent=2).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass  # 静默日志

        try:
            self._http_server = http.server.HTTPServer(
                (self._config.bind_host, self._config.bind_port), ClusterHTTPHandler
            )
            t = threading.Thread(target=self._http_server.serve_forever, daemon=True)
            t.start()
        except OSError:
            pass


# ──────────────────────────────────────────────
# 测试入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="天机v9.1 集群管理器")
    parser.add_argument("--role", choices=[r.value for r in NodeRole], default="leader")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--join", type=str, help="种子节点 host:port")
    parser.add_argument("--config", type=str, help="配置文件路径")

    args = parser.parse_args()

    config = ClusterConfig(
        role=NodeRole(args.role),
        bind_port=args.port,
        seed_nodes=[args.join] if args.join else [],
    )

    manager = ClusterManager(config)
    manager.start()

    print(f"集群节点 [{config.role.value}] 已启动")
    print(f"  节点ID: {manager._node_id}")
    print(f"  端口: {config.bind_port}")
    print(
        f"  API: http://{manager._get_local_ip()}:{config.bind_port}/api/cluster/status"
    )
    print("  按 Ctrl+C 退出...")

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        manager.stop()
        print("\n集群节点已停止")
