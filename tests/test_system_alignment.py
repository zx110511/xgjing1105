import sys

sys.path.insert(0, r"d:\元初系统\天机v9.1")

import time

import pytest

from core.shared.registry_reconciler import RegistryReconciler, run_one_reconcile
from core.shared.tool_category_mapper import DEFAULT_MAPPER, ToolCategoryMapper


class TestToolCategoryMapper:
    """验证ToolCategoryMapper：从能力矩阵正确派生工具分类"""

    def test_derive_all_categories(self):
        mapper = ToolCategoryMapper()
        categories = mapper.list_all_categories()
        assert len(categories) >= 14, (
            f"分类数量不足，期望>=14，实际{len(categories)}: {categories}"
        )
        expected_categories = [
            "memory_ops",
            "search",
            "llm_intel",
            "knowledge_graph",
            "context",
            "system",
            "conversation",
            "export",
            "agent",
            "advanced_memory",
            "command",
            "ops",
            "security",
            "performance",
        ]
        for cat in expected_categories:
            assert cat in categories, f"缺少分类: {cat}"

    def test_total_tool_count(self):
        mapper = ToolCategoryMapper()
        tools = mapper.list_all_tools()
        assert len(tools) >= 40, f"工具总数不足，期望>=40，实际{len(tools)}"

    def test_get_category_for_tool(self):
        mapper = ToolCategoryMapper()
        all_tools = mapper.list_all_tools()
        test_cases = [
            ("memory_recall", "memory_ops"),
            ("memory_remember", "memory_ops"),
            ("search_memories", "search"),
            ("system_status", "system"),
            ("agent_dispatch", "agent"),
            ("execute_command", "command"),
            ("scan_vulnerabilities", "security"),
            ("profile_function", "performance"),
        ]
        for tool_name, expected_category in test_cases:
            if tool_name in all_tools:
                category = mapper.get_category_for_tool(tool_name)
                assert category == expected_category, (
                    f"{tool_name}分类映射错误，期望{expected_category}，实际{category}"
                )

    def test_default_mapper_is_initialized(self):
        assert DEFAULT_MAPPER.is_initialized is True
        assert DEFAULT_MAPPER.get_category_count() > 0
        assert DEFAULT_MAPPER.get_tool_count() > 0


class TestRegistryReconciler:
    """验证RegistryReconciler：注册表对账功能"""

    def test_reconcile_method_executes(self):
        reconciler = RegistryReconciler()
        result = reconciler.reconcile()
        assert isinstance(result, dict), "对账结果应为字典"
        assert "status" in result, "对账结果缺少status字段"
        assert "reconcile_time" in result, "对账结果缺少reconcile_time字段"

    def test_reconcile_contains_diffs_info(self):
        result = run_one_reconcile()
        assert "diffs_count" in result, "对账结果缺少diffs_count字段"
        assert "diffs" in result, "对账结果缺少diffs列表"
        assert isinstance(result["diffs_count"], int), "diffs_count应为整数"
        assert isinstance(result["diffs"], list), "diffs应为列表"

    def test_reconcile_execution_time(self):
        reconciler = RegistryReconciler()
        reconciler.reconcile()
        start_time = time.time()
        reconciler.reconcile()
        elapsed_ms = (time.time() - start_time) * 1000
        assert elapsed_ms < 10000, (
            f"对账执行时间过长，期望<10000ms，实际{elapsed_ms:.2f}ms"
        )

    def test_reconcile_result_structure(self):
        result = run_one_reconcile()
        assert "summary" in result
        assert "suggestions" in result
        assert "grouped_diffs" in result
        assert isinstance(result["summary"], dict)
        assert isinstance(result["suggestions"], list)
        assert isinstance(result["grouped_diffs"], dict)


class TestExclusiveLockCheck:
    """验证后台进程排他性检查：端口+PID+健康检查三重验证"""

    def test_check_exclusive_lock_method_exists(self):
        from launcher.tianji_v91_launcher import TianjiLauncher

        launcher = TianjiLauncher()
        assert hasattr(launcher, "_check_exclusive_lock"), (
            "_check_exclusive_lock方法不存在"
        )

    def test_check_exclusive_lock_returns_tuple(self):
        from launcher.tianji_v91_launcher import TianjiLauncher

        launcher = TianjiLauncher()
        result = launcher._check_exclusive_lock()
        assert isinstance(result, tuple), "返回值应为元组"
        assert len(result) == 2, "返回值应包含2个元素"
        assert isinstance(result[0], bool), "第一个元素应为布尔值"
        assert isinstance(result[1], str), "第二个元素应为字符串"

    def test_check_exclusive_lock_validates_all_three_checks(self):
        from launcher.tianji_v91_launcher import TianjiLauncher

        launcher = TianjiLauncher()
        available, reason = launcher._check_exclusive_lock()
        if available:
            assert reason == "", "服务可用时原因应为空字符串"
        else:
            checks_present = any(
                check in reason for check in ["端口", "PID", "健康检查"]
            )
            assert checks_present, (
                f"排他性检查失败原因应包含端口/PID/健康检查信息，实际: {reason}"
            )


class TestTrayStatusSync:
    """验证托盘状态同步：状态获取与图标生成"""

    def test_get_service_status_exists(self):
        from launcher.tianji_tray import _get_service_status

        assert callable(_get_service_status), "_get_service_status方法不存在"

    def test_get_service_status_returns_valid_value(self):
        from launcher.tianji_tray import _get_service_status

        status = _get_service_status()
        valid_statuses = ["normal", "warning", "error", "stopped"]
        assert status in valid_statuses, (
            f"状态值无效，期望{valid_statuses}之一，实际{status}"
        )

    def test_create_tray_image_supports_status(self):
        from launcher.tianji_tray import create_tray_image

        valid_statuses = ["normal", "warning", "error", "stopped"]
        for status in valid_statuses:
            img = create_tray_image(status)
            assert img is not None, f"create_tray_image({status})返回None"
            assert hasattr(img, "size"), f"create_tray_image({status})返回非图像对象"
            assert img.size == (64, 64), f"图像尺寸应为64x64，实际{img.size}"

    def test_create_tray_image_default_status(self):
        from launcher.tianji_tray import create_tray_image

        img = create_tray_image()
        assert img is not None
        assert img.size == (64, 64)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
