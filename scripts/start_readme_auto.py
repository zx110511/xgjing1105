"""
天机v9.1 README自动化守护进程启动脚本
"""

import sys
import signal
import time
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.shared.readme_auto_system import READMEAutoSystem, create_default_config
from core.memory.hybrid_engine import ICMEStorageEngine

# 全局变量
auto_system = None


def signal_handler(signum, frame):
    """信号处理器"""
    global auto_system
    print("\n[信号] 收到终止信号，正在关闭...")
    if auto_system:
        auto_system.shutdown()
    sys.exit(0)


def main():
    global auto_system

    print("=" * 60)
    print("天机v9.1 README自动化守护进程")
    print("=" * 60)

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 初始化天机引擎
    print("\n[1] 初始化天机引擎...")
    try:
        engine = ICMEStorageEngine()
        print("  ✓ ICMEStorageEngine初始化成功")
    except Exception as e:
        print(f"  ✗ 引擎初始化失败: {e}")
        engine = None

    # 创建配置
    print("\n[2] 创建自动化配置...")
    config = create_default_config(str(project_root))
    print(f"  ✓ 监控目录数: {len(config.watch_dirs)}")
    for i, d in enumerate(config.watch_dirs[:5], 1):
        print(f"    {i}. {Path(d).name}")

    # 创建自动化系统
    print("\n[3] 创建自动化系统...")
    auto_system = READMEAutoSystem(engine=engine, config=config)

    # 初始化
    print("\n[4] 初始化自动化系统...")
    config_file = project_root / "config" / "readme_auto_config.json"
    auto_system.initialize(str(config_file))

    # 保存配置
    print("\n[5] 保存配置文件...")
    auto_system.save_config(str(config_file))

    # 显示统计
    print("\n[6] 系统统计:")
    stats = auto_system.get_stats()
    print(f"  运行状态: {'运行中' if stats['running'] else '已停止'}")
    print(f"  监控目录: {stats['watch_dirs']}")
    print(f"  watchdog可用: {'是' if stats['watchdog_available'] else '否'}")

    print("\n" + "=" * 60)
    print("README自动化守护进程已启动!")
    print("按 Ctrl+C 停止")
    print("=" * 60)

    # 主循环
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[关闭] 正在关闭自动化系统...")
        auto_system.shutdown()

        # 最终统计
        stats = auto_system.get_stats()
        print(f"\n最终统计:")
        print(f"  总更新次数: {stats['update_count']}")
        print(f"  最后更新时间: {stats['last_update_time']}")


if __name__ == "__main__":
    main()
