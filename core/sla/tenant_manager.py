"""
多租户管理器 v1.0
=================
基于现有 namespace_manager.py 增强:
  1. 租户注册/注销
  2. 租户级记忆隔离(共享SQLite+tenant_id字段)
  3. 租户级配额管理(条目数/存储大小/QPS)
  4. 租户级权限控制(读/写/管理)
  5. 租户使用量统计
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("tianji.sla.tenant")


class TenantRole(str, Enum):
    """租户角色"""
    READER = "reader"
    WRITER = "writer"
    ADMIN = "admin"


class TenantStatus(str, Enum):
    """租户状态"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


@dataclass
class TenantQuota:
    """租户配额"""
    max_entries: int = 50000
    max_storage_mb: float = 100.0
    max_qps: int = 50
    max_api_calls_per_month: int = 500000

    def check_entries(self, current: int) -> bool:
        """检查条目数是否超限"""
        return current < self.max_entries

    def check_storage(self, current_mb: float) -> bool:
        """检查存储是否超限"""
        return current_mb < self.max_storage_mb

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_entries": self.max_entries,
            "max_storage_mb": self.max_storage_mb,
            "max_qps": self.max_qps,
            "max_api_calls_per_month": self.max_api_calls_per_month,
        }


@dataclass
class Tenant:
    """租户实体"""
    tenant_id: str
    name: str
    status: TenantStatus = TenantStatus.ACTIVE
    role: TenantRole = TenantRole.WRITER
    quota: TenantQuota = field(default_factory=TenantQuota)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TenantUsage:
    """租户使用量"""
    tenant_id: str
    entry_count: int = 0
    storage_mb: float = 0.0
    api_calls_this_month: int = 0
    current_qps: float = 0.0
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "entry_count": self.entry_count,
            "storage_mb": self.storage_mb,
            "api_calls_this_month": self.api_calls_this_month,
            "current_qps": self.current_qps,
        }


class TenantIsolation:
    """租户数据隔离层"""

    def __init__(self) -> None:
        self._tenant_data: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self._lock = threading.Lock()

    def store(self, tenant_id: str, layer: str, entry: Dict[str, Any]) -> None:
        """存储租户数据"""
        with self._lock:
            if tenant_id not in self._tenant_data:
                self._tenant_data[tenant_id] = {}
            if layer not in self._tenant_data[tenant_id]:
                self._tenant_data[tenant_id][layer] = []
            self._tenant_data[tenant_id][layer].append(entry)

    def retrieve(
        self, tenant_id: str, layer: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """检索租户数据"""
        with self._lock:
            layers = self._tenant_data.get(tenant_id, {})
            return layers.get(layer, [])[:limit]

    def delete(self, tenant_id: str, entry_id: str) -> bool:
        """删除租户指定条目"""
        with self._lock:
            layers = self._tenant_data.get(tenant_id, {})
            for layer_data in layers.values():
                for i, entry in enumerate(layer_data):
                    if entry.get("id") == entry_id:
                        layer_data.pop(i)
                        return True
        return False

    def count_entries(self, tenant_id: str) -> int:
        """统计租户条目数"""
        with self._lock:
            layers = self._tenant_data.get(tenant_id, {})
            return sum(len(v) for v in layers.values())

    def clear_tenant(self, tenant_id: str) -> int:
        """清除租户所有数据"""
        with self._lock:
            layers = self._tenant_data.get(tenant_id, {})
            count = sum(len(v) for v in layers.values())
            self._tenant_data.pop(tenant_id, None)
            return count

    def list_layers(self, tenant_id: str) -> List[str]:
        """列出租户的所有层"""
        with self._lock:
            return list(self._tenant_data.get(tenant_id, {}).keys())


class TenantManager:
    """多租户管理器"""

    DEFAULT_TENANT_ID = "default"

    def __init__(self) -> None:
        self._tenants: Dict[str, Tenant] = {}
        self._usage: Dict[str, TenantUsage] = {}
        self._isolation = TenantIsolation()
        self._lock = threading.Lock()

        # 注册默认租户
        self._register_default()

    def _register_default(self) -> None:
        """注册默认租户"""
        default = Tenant(
            tenant_id=self.DEFAULT_TENANT_ID,
            name="Default Tenant",
            role=TenantRole.ADMIN,
            quota=TenantQuota(
                max_entries=100000,
                max_storage_mb=500.0,
                max_qps=200,
                max_api_calls_per_month=5000000,
            ),
        )
        self._tenants[default.tenant_id] = default
        self._usage[default.tenant_id] = TenantUsage(tenant_id=default.tenant_id)

    def register_tenant(
        self,
        name: str,
        role: TenantRole = TenantRole.WRITER,
        quota: Optional[TenantQuota] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tenant:
        """注册新租户"""
        tenant_id = f"tenant-{uuid.uuid4().hex[:12]}"
        tenant = Tenant(
            tenant_id=tenant_id,
            name=name,
            role=role,
            quota=quota or TenantQuota(),
            metadata=metadata or {},
        )
        with self._lock:
            self._tenants[tenant_id] = tenant
            self._usage[tenant_id] = TenantUsage(tenant_id=tenant_id)
        logger.info("租户注册: %s (%s)", name, tenant_id)
        return tenant

    def unregister_tenant(self, tenant_id: str) -> bool:
        """注销租户(软删除)"""
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if tenant is None or tenant_id == self.DEFAULT_TENANT_ID:
                return False
            tenant.status = TenantStatus.DELETED
            self._isolation.clear_tenant(tenant_id)
        logger.info("租户注销: %s", tenant_id)
        return True

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """获取租户信息"""
        return self._tenants.get(tenant_id)

    def list_tenants(self, include_deleted: bool = False) -> List[Tenant]:
        """列出所有租户"""
        tenants = list(self._tenants.values())
        if not include_deleted:
            tenants = [t for t in tenants if t.status != TenantStatus.DELETED]
        return tenants

    def check_permission(
        self, tenant_id: str, required_role: TenantRole
    ) -> bool:
        """检查租户权限"""
        tenant = self._tenants.get(tenant_id)
        if tenant is None or tenant.status != TenantStatus.ACTIVE:
            return False
        role_hierarchy = {
            TenantRole.READER: 1,
            TenantRole.WRITER: 2,
            TenantRole.ADMIN: 3,
        }
        return role_hierarchy.get(tenant.role, 0) >= role_hierarchy.get(
            required_role, 99
        )

    def check_quota(self, tenant_id: str) -> Dict[str, bool]:
        """检查租户配额"""
        tenant = self._tenants.get(tenant_id)
        usage = self._usage.get(tenant_id)
        if tenant is None or usage is None:
            return {"entries": False, "storage": False, "qps": False}

        return {
            "entries": tenant.quota.check_entries(usage.entry_count),
            "storage": tenant.quota.check_storage(usage.storage_mb),
            "qps": usage.current_qps < tenant.quota.max_qps,
        }

    def record_usage(
        self,
        tenant_id: str,
        entries_delta: int = 0,
        storage_delta_mb: float = 0.0,
        api_call: bool = False,
    ) -> None:
        """记录租户使用量"""
        with self._lock:
            usage = self._usage.get(tenant_id)
            if usage is None:
                return
            usage.entry_count += entries_delta
            usage.storage_mb += storage_delta_mb
            if api_call:
                usage.api_calls_this_month += 1
            usage.last_updated = time.time()

    def get_usage(self, tenant_id: str) -> Optional[TenantUsage]:
        """获取租户使用量"""
        return self._usage.get(tenant_id)

    def store_memory(
        self, tenant_id: str, layer: str, entry: Dict[str, Any]
    ) -> bool:
        """存储租户记忆(带配额检查)"""
        if not self.check_permission(tenant_id, TenantRole.WRITER):
            return False
        quota = self.check_quota(tenant_id)
        if not quota.get("entries", True):
            logger.warning("租户 %s 条目数超限", tenant_id)
            return False
        self._isolation.store(tenant_id, layer, entry)
        self.record_usage(tenant_id, entries_delta=1, api_call=True)
        return True

    def retrieve_memory(
        self, tenant_id: str, layer: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """检索租户记忆(带权限检查)"""
        if not self.check_permission(tenant_id, TenantRole.READER):
            return []
        self.record_usage(tenant_id, api_call=True)
        return self._isolation.retrieve(tenant_id, layer, limit)

    @property
    def isolation(self) -> TenantIsolation:
        """获取隔离层"""
        return self._isolation
