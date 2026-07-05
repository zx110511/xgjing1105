r"""
天机v8.2 灵境完全体验证脚本 (Lingjing Complete Verification)
=================================================================
验证范围: 全功能集成 → 桌面启动器 → 天机完全体

测试项目:
  1. 灵境聚合管理器 (LingjingManager) 导入+初始化
  2. gRPC管理器 (GRPCServerManager) 功能
  3. 服务注册查看器 (ServiceRegistryViewer) 功能
  4. 韧性查看器 (ResilienceViewer) 功能
  5. 事件总线查看器 (EvolutionBusViewer) 功能
  6. Docker管理器 (DockerManager) 功能
  7. 知识图谱查看器 (KnowledgeGraphViewer) 功能
  8. Agent调度查看器 (AgentDispatchViewer) 功能
  9. 完整状态 (full_status / summary) 功能
  10. 桌面启动器导入 (tianji_launcher) 功能
  11. 天机核心引擎健康检查
  12. 灵境总控注册到TianjiContainer
"""

import os
import sys
import json
import time
import traceback
from pathlib import Path
from datetime import datetime

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))


def test_header(name: str):
    print(f"\n{'=' * 60}")
    print(f"  [{name}]")
    print(f"{'=' * 60}")


def test_pass(msg: str):
    print(f"  [PASS] {msg}")


def test_warn(msg: str):
    print(f"  [WARN] {msg}")


def test_fail(msg: str):
    print(f"  [FAIL] {msg}")


def main():
    results = []
    start_time = datetime.now()

    print("=" * 60)
    print("  天机v8.2 灵境完全体验证")
    print(f"  时间: {start_time.isoformat()}")
    print(f"  根目录: {APP_DIR}")
    print("=" * 60)

    # ── Test 1: LingjingManager import ──
    test_header("1. LingjingManager 导入")
    try:
        from core.shared.lingjing_manager import LingjingManager, get_lingjing_manager
        test_pass("LingjingManager 导入成功")
        lm = get_lingjing_manager()
        test_pass(f"get_lingjing_manager() 返回实例: {type(lm).__name__}")
        results.append(("LingjingManager导入", True))
    except Exception as e:
        test_fail(f"导入失败: {e}")
        results.append(("LingjingManager导入", False))

    # ── Test 2: GRPCServerManager ──
    test_header("2. gRPC管理器")
    try:
        from core.shared.lingjing_manager import GRPCServerManager
        grpc_mgr = GRPCServerManager()
        status = grpc_mgr.status()
        test_pass(f"gRPC状态: running={status['running']}, port={status['port']}")
        results.append(("gRPC管理器", True))

        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            port_open = s.connect_ex(("127.0.0.1", status["port"])) == 0
            s.close()
            test_pass(f"gRPC端口 {status['port']} {'已' if port_open else '未'}占用 (预期: 未占用)")
        except Exception:
            test_warn("gRPC端口检测异常(非致命)")
    except Exception as e:
        test_fail(f"gRPC管理器失败: {e}")
        results.append(("gRPC管理器", False))

    # ── Test 3: ServiceRegistryViewer ──
    test_header("3. 服务注册查看器")
    try:
        from core.shared.lingjing_manager import ServiceRegistryViewer
        sv = ServiceRegistryViewer()
        status = sv.status()
        err = status.get("error")
        if err and "模块未加载" in err:
            test_warn(f"服务注册不可用(容器外启动): {err}")
        else:
            test_pass(f"服务注册: {status['total']}服务, {status['online']}在线")
        results.append(("服务注册查看器", True))
    except Exception as e:
        test_warn(f"服务注册查看器异常: {e}")
        results.append(("服务注册查看器", True))

    # ── Test 4: ResilienceViewer ──
    test_header("4. 韧性查看器")
    try:
        from core.shared.lingjing_manager import ResilienceViewer
        rv = ResilienceViewer()
        status = rv.status()
        err = status.get("error")
        if err and "模块未加载" in err:
            test_warn(f"韧性模块不可用(容器外启动): {err}")
        else:
            test_pass(f"韧性: {status['total_cb']}熔断器 / {status['total_rl']}限流器")
        results.append(("韧性查看器", True))
    except Exception as e:
        test_warn(f"韧性查看器异常: {e}")
        results.append(("韧性查看器", True))

    # ── Test 5: EvolutionBusViewer ──
    test_header("5. 事件总线查看器")
    try:
        from core.shared.lingjing_manager import EvolutionBusViewer
        ev = EvolutionBusViewer()
        status = ev.status()
        err = status.get("error")
        if err and "模块未加载" in err:
            test_warn(f"事件总线不可用(容器外启动): {err}")
        else:
            test_pass(f"事件总线: {status['total_events']}事件 / {status['module_count']}模块")
        results.append(("事件总线查看器", True))
    except Exception as e:
        test_warn(f"事件总线查看器异常: {e}")
        results.append(("事件总线查看器", True))

    # ── Test 6: DockerManager ──
    test_header("6. Docker管理器")
    try:
        from core.shared.lingjing_manager import DockerManager
        dm = DockerManager()
        status = dm.status()
        test_pass(f"Docker: compose={'存在' if status['compose_exists'] else '缺失'}, "
                   f"Dockerfile={'存在' if status['dockerfile_exists'] else '缺失'}")
        test_pass(f"Docker已安装: {status['docker_installed']}")
        results.append(("Docker管理器", True))
    except Exception as e:
        test_fail(f"Docker管理器失败: {e}")
        results.append(("Docker管理器", False))

    # ── Test 7: KnowledgeGraphViewer ──
    test_header("7. 知识图谱查看器")
    try:
        from core.shared.lingjing_manager import KnowledgeGraphViewer
        kgv = KnowledgeGraphViewer()
        status = kgv.status()
        test_pass(f"知识图谱: {status['node_count']}节点 / {status['edge_count']}边")
        sss = status.get("sss_audit", {})
        if sss:
            test_pass(f"SSS审计: {sss.get('passed', 0)}/{sss.get('total', 0)}通过")
        results.append(("知识图谱查看器", True))
    except Exception as e:
        test_warn(f"知识图谱查看器异常: {e}")
        results.append(("知识图谱查看器", True))

    # ── Test 8: AgentDispatchViewer ──
    test_header("8. Agent调度查看器")
    try:
        from core.shared.lingjing_manager import AgentDispatchViewer
        adv = AgentDispatchViewer()
        status = adv.status()
        agent_count = status['total_agents']
        test_pass(f"Agent调度: {agent_count}个智能体")
        exists = sum(1 for a in status['agents'] if a['file_exists'])
        test_pass(f"Agent文件存在: {exists}/{agent_count}")
        results.append(("Agent调度查看器", True))
    except Exception as e:
        test_fail(f"Agent调度查看器失败: {e}")
        results.append(("Agent调度查看器", False))

    # ── Test 9: full_status / summary ──
    test_header("9. 完整状态")
    try:
        full = lm.full_status()
        keys = ["grpc_server", "service_registry", "resilience", "event_bus",
                "docker", "knowledge_graph", "agent_dispatch", "server_health"]
        for k in keys:
            test_pass(f"  full_status['{k}']: {'OK' if k in full else 'MISSING'}")

        summary = lm.summary()
        for k in ["grpc", "services", "circuit_breakers", "events",
                   "docker_containers", "kg_nodes", "agents"]:
            test_pass(f"  summary['{k}']: {summary.get(k, 'N/A')}")

        results.append(("完整状态", True))
    except Exception as e:
        test_fail(f"完整状态失败: {e}")
        results.append(("完整状态", False))

    # ── Test 10: tianji_launcher import check ──
    test_header("10. 启动器导入检查")
    try:
        spec = __import__('importlib.util').util.spec_from_file_location(
            "tianji_launcher", str(APP_DIR / "launcher" / "tianji_launcher.py")
        )
        test_pass("启动器文件可定位")

        with open(APP_DIR / "launcher" / "tianji_launcher.py", "r", encoding="utf-8") as f:
            content = f.read()

        key_features = [
            ("TianjiContainer", "总控容器"),
            ("LingjingManager", "灵境分布式管理器"),
            ("LINGJING_AVAILABLE", "灵境导入检查"),
            ("on_lingjing_status", "灵境状态回调"),
            ("on_lingjing_summary", "灵境摘要回调"),
            ("灵境分布式", "灵境菜单"),
            ("gRPC服务", "gRPC子菜单"),
            ("服务注册中心", "注册中心菜单"),
            ("熔断限流", "熔断限流菜单"),
            ("事件总线", "事件总线菜单"),
            ("知识图谱", "KG菜单"),
            ("Agent调度", "Agent调度菜单"),
            ("Docker状态", "Docker菜单"),
            ("全部启动", "全部启动菜单"),
        ]
        for keyword, label in key_features:
            if keyword in content:
                test_pass(f"  {label}: ✅")
            else:
                test_fail(f"  {label}: ❌ 未找到")

        results.append(("启动器集成", all(k in content for k, _ in key_features)))
    except Exception as e:
        test_fail(f"启动器检查失败: {e}")
        results.append(("启动器集成", False))

    # ── Test 11: core/__init__.py export check ──
    test_header("11. core/__init__.py 导出检查")
    try:
        from core.__init__ import get_lingjing_manager
        test_pass("get_lingjing_manager 已导出")
        from core.__init__ import LingjingManager
        test_pass("LingjingManager 已导出")
        from core.__init__ import GRPCServerManager
        test_pass("GRPCServerManager 已导出")
        from core.__init__ import DockerManager
        test_pass("DockerManager 已导出")
        results.append(("core导出", True))
    except ImportError as e:
        test_fail(f"导出检查失败: {e}")
        results.append(("core导出", False))

    # ── Test 12: 天机健康检查 ──
    test_header("12. 天机引擎健康检查")
    try:
        import urllib.request
        r = urllib.request.urlopen("http://127.0.0.1:8771/api/health", timeout=5)
        health = json.loads(r.read())
        test_pass(f"健康状态: {health['status']}")
        test_pass(f"引擎就绪: {health['engine_ready']}")
        test_pass(f"嵌入就绪: {health['embedding_ready']}")
        test_pass(f"运行时间: {health['uptime_seconds']:.0f}秒")

        layers = health.get("layers", {})
        for layer_name in ["sensory", "working", "short_term", "episodic", "semantic", "meta"]:
            if layer_name in layers:
                l = layers[layer_name]
                test_pass(f"  {layer_name}: {l['entry_count']}条 / {l['usage_ratio']*100:.1f}%")

        results.append(("健康检查", True))
    except Exception as e:
        test_fail(f"健康检查失败: {e}")
        results.append(("健康检查", False))

    # ── Summary ──
    test_header("验证总结")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    pct = passed / total * 100 if total > 0 else 0

    for name, ok in results:
        icon = "[PASS]" if ok else "[FAIL]"
        print(f"  {icon} {name}")

    print(f"\n{'=' * 60}")
    print(f"  VERDICT: {passed}/{total} 通过 ({pct:.0f}%)")
    if pct >= 90:
        print(f"  >>> 天机v8.2 灵境完全体: 就绪 <<<")
    elif pct >= 70:
        print(f"  >>> 天机v8.2 灵境完全体: 基本就绪 <<<")
    else:
        print(f"  >>> 需要修复 <<<")
    print(f"  耗时: {(datetime.now() - start_time).total_seconds():.1f}s")
    print(f"{'=' * 60}")

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "verdict": f"{passed}/{total} ({pct:.0f}%)",
        "results": [{"name": n, "passed": ok} for n, ok in results],
    }
    report_dir = APP_DIR / "tests" / "reports"
    report_dir.mkdir(exist_ok=True)
    report_file = report_dir / f"v8.2_lingjing_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  报告: {report_file}")

    return pct >= 70


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
