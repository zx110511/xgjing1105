"""D2: 多租户隔离测试"""
import time
import threading

import pytest

from core.sla.tenant_manager import (
    Tenant,
    TenantIsolation,
    TenantManager,
    TenantQuota,
    TenantRole,
    TenantStatus,
    TenantUsage,
)


class TestTenantQuota:
    def test_default_quota(self):
        q = TenantQuota()
        assert q.max_entries == 50000
        assert q.max_storage_mb == 100.0

    def test_check_entries(self):
        q = TenantQuota(max_entries=100)
        assert q.check_entries(50) is True
        assert q.check_entries(100) is False

    def test_check_storage(self):
        q = TenantQuota(max_storage_mb=10.0)
        assert q.check_storage(5.0) is True
        assert q.check_storage(10.0) is False

    def test_to_dict(self):
        q = TenantQuota()
        d = q.to_dict()
        assert "max_entries" in d
        assert "max_qps" in d


class TestTenantIsolation:
    def test_store_and_retrieve(self):
        iso = TenantIsolation()
        iso.store("t1", "working", {"id": "e1", "content": "hello"})
        results = iso.retrieve("t1", "working")
        assert len(results) == 1
        assert results[0]["content"] == "hello"

    def test_isolation_between_tenants(self):
        iso = TenantIsolation()
        iso.store("t1", "working", {"id": "e1", "content": "tenant1"})
        iso.store("t2", "working", {"id": "e2", "content": "tenant2"})
        assert iso.retrieve("t1", "working")[0]["content"] == "tenant1"
        assert iso.retrieve("t2", "working")[0]["content"] == "tenant2"
        # t1看不到t2的数据
        assert len(iso.retrieve("t1", "working")) == 1

    def test_delete_entry(self):
        iso = TenantIsolation()
        iso.store("t1", "working", {"id": "e1", "content": "hello"})
        assert iso.delete("t1", "e1") is True
        assert len(iso.retrieve("t1", "working")) == 0

    def test_delete_nonexistent(self):
        iso = TenantIsolation()
        assert iso.delete("t1", "nonexistent") is False

    def test_count_entries(self):
        iso = TenantIsolation()
        iso.store("t1", "working", {"id": "e1"})
        iso.store("t1", "episodic", {"id": "e2"})
        assert iso.count_entries("t1") == 2

    def test_clear_tenant(self):
        iso = TenantIsolation()
        iso.store("t1", "working", {"id": "e1"})
        count = iso.clear_tenant("t1")
        assert count == 1
        assert iso.count_entries("t1") == 0

    def test_list_layers(self):
        iso = TenantIsolation()
        iso.store("t1", "working", {"id": "e1"})
        iso.store("t1", "episodic", {"id": "e2"})
        layers = iso.list_layers("t1")
        assert "working" in layers
        assert "episodic" in layers


class TestTenantManager:
    def test_default_tenant_exists(self):
        tm = TenantManager()
        default = tm.get_tenant("default")
        assert default is not None
        assert default.role == TenantRole.ADMIN

    def test_register_tenant(self):
        tm = TenantManager()
        tenant = tm.register_tenant("Test Corp")
        assert tenant.name == "Test Corp"
        assert tenant.status == TenantStatus.ACTIVE

    def test_unregister_tenant(self):
        tm = TenantManager()
        tenant = tm.register_tenant("Test Corp")
        assert tm.unregister_tenant(tenant.tenant_id) is True
        assert tm.get_tenant(tenant.tenant_id).status == TenantStatus.DELETED

    def test_cannot_unregister_default(self):
        tm = TenantManager()
        assert tm.unregister_tenant("default") is False

    def test_list_tenants(self):
        tm = TenantManager()
        tm.register_tenant("A")
        tm.register_tenant("B")
        tenants = tm.list_tenants()
        assert len(tenants) >= 3  # default + A + B

    def test_permission_reader(self):
        tm = TenantManager()
        tenant = tm.register_tenant("Reader", role=TenantRole.READER)
        assert tm.check_permission(tenant.tenant_id, TenantRole.READER) is True
        assert tm.check_permission(tenant.tenant_id, TenantRole.WRITER) is False

    def test_permission_writer(self):
        tm = TenantManager()
        tenant = tm.register_tenant("Writer", role=TenantRole.WRITER)
        assert tm.check_permission(tenant.tenant_id, TenantRole.WRITER) is True
        assert tm.check_permission(tenant.tenant_id, TenantRole.ADMIN) is False

    def test_permission_suspended(self):
        tm = TenantManager()
        tenant = tm.register_tenant("Suspended")
        tenant.status = TenantStatus.SUSPENDED
        assert tm.check_permission(tenant.tenant_id, TenantRole.READER) is False

    def test_quota_check(self):
        tm = TenantManager()
        tenant = tm.register_tenant("QuotaTest", quota=TenantQuota(max_entries=5))
        quota = tm.check_quota(tenant.tenant_id)
        assert quota["entries"] is True

    def test_quota_exceeded(self):
        tm = TenantManager()
        tenant = tm.register_tenant("OverQuota", quota=TenantQuota(max_entries=2))
        # 模拟使用量
        usage = tm.get_usage(tenant.tenant_id)
        usage.entry_count = 3
        quota = tm.check_quota(tenant.tenant_id)
        assert quota["entries"] is False

    def test_store_memory(self):
        tm = TenantManager()
        tenant = tm.register_tenant("Writer", role=TenantRole.WRITER)
        result = tm.store_memory(tenant.tenant_id, "working", {"id": "e1", "content": "test"})
        assert result is True

    def test_store_memory_reader_denied(self):
        tm = TenantManager()
        tenant = tm.register_tenant("Reader", role=TenantRole.READER)
        result = tm.store_memory(tenant.tenant_id, "working", {"id": "e1"})
        assert result is False

    def test_retrieve_memory(self):
        tm = TenantManager()
        tenant = tm.register_tenant("Writer", role=TenantRole.WRITER)
        tm.store_memory(tenant.tenant_id, "working", {"id": "e1", "content": "hello"})
        results = tm.retrieve_memory(tenant.tenant_id, "working")
        assert len(results) == 1

    def test_retrieve_memory_unauthorized(self):
        tm = TenantManager()
        tenant = tm.register_tenant("Suspended")
        tenant.status = TenantStatus.SUSPENDED
        results = tm.retrieve_memory(tenant.tenant_id, "working")
        assert results == []

    def test_record_usage(self):
        tm = TenantManager()
        tenant = tm.register_tenant("Usage")
        tm.record_usage(tenant.tenant_id, entries_delta=5, storage_delta_mb=1.5, api_call=True)
        usage = tm.get_usage(tenant.tenant_id)
        assert usage.entry_count == 5
        assert usage.storage_mb == 1.5
        assert usage.api_calls_this_month == 1
