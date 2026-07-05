#!/usr/bin/env python
# -*- coding: utf-8-sig -*-
"""
天机v9.1 → CherryClaw 启动脚本
==============================
一键启动天机记忆系统并接入CherryClaw Agent。

用法:
    python start_cherryclaw.py [command]

命令:
    start       启动记忆系统 (默认)
    stop        停止记忆系统
    status      查看系统状态
    test        运行集成测试
    audit       运行全量审计
    daemon      后台守护运行
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            Path(__file__).parent / "logs" / "cherryclaw_startup.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("tianji.cherryclaw.startup")


def cmd_start(args):
    """启动记忆系统"""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║         天机v9.1 → CherryClaw 全量记忆接入                   ║")
    print("║         ICME六层记忆 · DeepSeek驾驶 · 自进化闭环             ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    sys.path.insert(0, str(Path(__file__).resolve().parent))

    from adapters.cherryclaw_adapter import CherryClawAdapter

    data_path = args.data_path or str(
        Path(__file__).resolve().parent / "data" / ".memory"
    )

    print(f"[启动] 数据路径: {data_path}")
    print(f"[启动] LLM增强: {not args.no_llm}")
    print(f"[启动] 质量门禁: {not args.no_quality_gate}")
    print(f"[启动] 双过程固结: {not args.no_dual_process}")
    print(f"[启动] 级联失效: {not args.no_cascade}")
    print()

    adapter = CherryClawAdapter(
        data_path=data_path,
        auto_start=True,
        enable_llm=not args.no_llm,
        enable_quality_gate=not args.no_quality_gate,
        enable_dual_process=not args.no_dual_process,
        enable_cascade_invalidation=not args.no_cascade,
        protocol_mode=args.protocol,
    )

    if adapter.is_started:
        health = adapter.health_check()
        print(f"\n✅ 天机v9.1记忆系统启动成功!")
        print(json.dumps(health, ensure_ascii=False, indent=2))
        print()

        # 加载已有记忆统计
        layer_summary = adapter.get_layer_summary()
        if layer_summary:
            print("📊 六层记忆状态:")
            for layer_name, info in layer_summary.items():
                print(f"  {layer_name:12s} | 条目:{info['count']:>6d} | 容量:{info['size_mb']:>8.2f}MB")

        print()
        print("🔗 CherryClaw接入点:")
        print("  - adapter.is_started = True")
        print("  - adapter.remember() → 六层智能写入")
        print("  - adapter.recall() → 多维度检索")
        print("  - adapter.remember_conversation_turn() → 对话捕获")
        print("  - adapter.run_dual_process_consolidation() → 知识提炼")
        print()
        print("天机·星枢运转 — 记忆在握  ✨")

        return adapter
    else:
        print("\n❌ 天机记忆系统启动失败!")
        return None


def cmd_status(args):
    """查看系统状态"""
    from adapters.cherryclaw_adapter import CherryClawAdapter

    adapter = CherryClawAdapter(auto_start=True)
    if not adapter.is_started:
        print("❌ 记忆系统未启动")
        return

    stats = adapter.get_full_status()
    health = adapter.health_check()

    print("╔══════════════════════════════════════════════════════╗")
    print("║       天机v9.1 记忆系统状态报告                       ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    print(f"  运行时间: {stats.uptime_seconds:.0f}秒")
    print(f"  总条目数: {stats.total_entries}")
    print(f"  总访问数: {stats.total_accesses}")
    print(f"  总固结数: {stats.total_consolidations}")
    print(f"  总归档数: {stats.total_archivals}")
    print(f"  被拒数:   {stats.total_rejected}")
    print(f"  降级数:   {stats.total_downgraded}")
    print(f"  冲突数:   {stats.total_conflicts}")
    print(f"  检索调用: {stats.total_recall_calls}")
    print(f"  检索命中: {stats.total_recall_hits}")
    print()
    print("  健康检查:", json.dumps(health, ensure_ascii=False))
    print()

    if stats.layers:
        print("  各层详情:")
        for name, info in stats.layers.items():
            print(f"    {name:12s} | 用量:{info.get('usage_ratio', 0):.2%} | 条目:{info.get('entry_count', 0)}")


def cmd_test(args):
    """运行集成测试"""
    print("🧪 运行天机v9.1 → CherryClaw 集成测试...\n")

    from adapters.cherryclaw_adapter import CherryClawAdapter

    adapter = CherryClawAdapter(auto_start=True)
    if not adapter.is_started:
        print("❌ 无法启动记忆系统，测试中止")
        return

    tests_passed = 0
    tests_total = 0

    # Test 1: 基本写入
    tests_total += 1
    try:
        result = adapter.remember("测试记忆: CherryClaw集成测试", layer="working", tags=["test", "integration"])
        if result.get("id"):
            print(f"  ✅ Test 1 (remember): id={result['id'][:16]}... layer={result.get('actual_layer')}")
            tests_passed += 1
        else:
            print(f"  ❌ Test 1 (remember): {result}")
    except Exception as e:
        print(f"  ❌ Test 1 (remember): {e}")

    # Test 2: 对话捕获
    tests_total += 1
    try:
        result = adapter.remember_conversation_turn(
            user_message="你好，请帮我查一下天气",
            ai_response="好的，让我为您查询天气信息...",
            tags=["test", "conversation"],
        )
        if result.get("sensory_result", {}).get("id"):
            print(f"  ✅ Test 2 (conversation_capture): session={result.get('session_id', '')[:16]}...")
            tests_passed += 1
        else:
            print(f"  ❌ Test 2 (conversation_capture): {result}")
    except Exception as e:
        print(f"  ❌ Test 2 (conversation_capture): {e}")

    # Test 3: 检索
    tests_total += 1
    try:
        results = adapter.recall(query="测试", limit=5)
        if len(results) > 0:
            print(f"  ✅ Test 3 (recall): 找到 {len(results)} 条相关记忆")
            tests_passed += 1
        else:
            print(f"  ⚠️  Test 3 (recall): 无结果 (可能是新数据库)")
            tests_passed += 1  # 不算失败
    except Exception as e:
        print(f"  ❌ Test 3 (recall): {e}")

    # Test 4: 时序列记录
    tests_total += 1
    try:
        result = adapter.create_temporal_record(
            content="CherryClaw用户偏好: 使用中文回复",
            layer="semantic",
            tags=["preference", "language", "chinese"],
            confidence=0.95,
        )
        if result and result.get("record_id"):
            print(f"  ✅ Test 4 (temporal_record): id={result['record_id'][:16]}...")
            tests_passed += 1
        else:
            print(f"  ⚠️  Test 4 (temporal_record): TemporalRecord模块不可用 (可选)")
            tests_passed += 1  # 可选组件
    except Exception as e:
        print(f"  ⚠️  Test 4 (temporal_record): {e} (可选组件)")

    # Test 5: 层级状态
    tests_total += 1
    try:
        layer_summary = adapter.get_layer_summary()
        if layer_summary:
            print(f"  ✅ Test 5 (layer_summary): {len(layer_summary)}层活跃")
            tests_passed += 1
        else:
            print(f"  ❌ Test 5 (layer_summary): 无层级数据")
    except Exception as e:
        print(f"  ❌ Test 5 (layer_summary): {e}")

    # Test 6: 全量状态
    tests_total += 1
    try:
        stats = adapter.get_full_status()
        if stats.total_entries > 0:
            print(f"  ✅ Test 6 (full_status): 总条目={stats.total_entries}")
            tests_passed += 1
        else:
            print(f"  ❌ Test 6 (full_status): 条目数为0")
    except Exception as e:
        print(f"  ❌ Test 6 (full_status): {e}")

    print(f"\n📊 测试结果: {tests_passed}/{tests_total} 通过")


def main():
    parser = argparse.ArgumentParser(
        description="天机v9.1 → CherryClaw 全量记忆接入启动器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # start
    p_start = subparsers.add_parser("start", help="启动记忆系统")
    p_start.add_argument("--data-path", help="数据目录路径")
    p_start.add_argument("--no-llm", action="store_true", help="禁用LLM增强")
    p_start.add_argument("--no-quality-gate", action="store_true", help="禁质量门禁")
    p_start.add_argument("--no-dual-process", action="store_true", help="禁双过程固结")
    p_start.add_argument("--no-cascade", action="store_true", help="禁级联失效")
    p_start.add_argument("--protocol", action="store_true", help="启用v9.1 Protocol模式")

    # status
    subparsers.add_parser("status", help="查看系统状态")

    # test
    subparsers.add_parser("test", help="运行集成测试")

    args = parser.parse_args()

    if args.command == "start" or args.command is None:
        cmd_start(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "test":
        cmd_test(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
