"""
天机v9.1 README索引体系集成脚本
为天机核心目录生成智能README.md
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.shared.directory_index import TianjiREADMEIntegrator, AutoREADMEManager
from core.memory.hybrid_engine import ICMEStorageEngine

def main():
    print("=" * 60)
    print("天机v9.1 README索引体系集成")
    print("=" * 60)

    # 初始化天机引擎
    print("\n[1] 初始化天机引擎...")
    try:
        engine = ICMEStorageEngine()
        print("  ✓ ICMEStorageEngine初始化成功")
    except Exception as e:
        print(f"  ✗ 引擎初始化失败: {e}")
        engine = None

    # 创建集成器
    print("\n[2] 创建README集成器...")
    integrator = TianjiREADMEIntegrator(engine=engine, registry=None)
    print("  ✓ TianjiREADMEIntegrator创建成功")

    # 定义要生成README的核心目录
    core_dirs = [
        "core",
        "indexing",
        "server",
        "server/api",
        "agents",
        "mcp",
        "web",
        "web/src",
        "web/src/pages",
        "active_memory",
        "adapters",
        "config",
        "daemon",
        "launcher",
    ]

    print(f"\n[3] 为{len(core_dirs)}个核心目录生成智能README.md...")
    print("-" * 60)

    success_count = 0
    for dir_name in core_dirs:
        dir_path = project_root / dir_name
        if not dir_path.exists():
            print(f"  ✗ {dir_name}: 目录不存在")
            continue

        try:
            readme_content = integrator.scan_and_generate(
                str(dir_path),
                max_depth=2,
                save_to_file=True
            )
            success_count += 1
            print(f"  ✓ {dir_name}: README.md生成成功 ({len(readme_content)}字符)")
        except Exception as e:
            print(f"  ✗ {dir_name}: {e}")

    print("-" * 60)
    print(f"  成功: {success_count}/{len(core_dirs)}")

    # 为根目录生成README.md（不覆盖现有）
    print(f"\n[4] 更新根目录README.md的动态区块...")
    root_readme = project_root / "README.md"
    if root_readme.exists():
        print(f"  根目录README.md已存在，跳过覆盖")
        print(f"  提示: 可手动调用 integrator.update_section() 更新特定区块")
    else:
        print(f"  根目录README.md不存在，生成新文件...")
        integrator.scan_and_generate(str(project_root), max_depth=1, save_to_file=True)

    # 演示AI钩子执行
    print(f"\n[5] 演示AI钩子解析...")
    from core.shared.directory_index import AIHookExecutor
    executor = AIHookExecutor(engine=engine)

    sample_readme = project_root / "core" / "README.md"
    if sample_readme.exists():
        hooks = executor.parse_hooks_from_readme(str(sample_readme))
        print(f"  从 core/README.md 解析到 {len(hooks)} 个钩子")
        for hook in hooks:
            print(f"    - {hook.hook_name}: {hook.action}")

    # 演示自动管理器
    print(f"\n[6] 创建自动管理器...")
    manager = AutoREADMEManager(engine=engine, registry=None)
    manager.watch_directory(str(project_root / "core"))
    manager.watch_directory(str(project_root / "indexing"))
    print(f"  ✓ AutoREADMEManager创建成功")
    print(f"  监控目录数: {len(manager._watch_paths)}")
    print(f"  提示: 调用 manager.start_auto_update() 启动守护进程")

    # 存储到天机
    if engine:
        print(f"\n[7] 存储到天机L4 Semantic层...")
        try:
            engine.remember(
                content=f"【README索引体系】集成完成\n成功生成{success_count}个README.md\n核心目录: {', '.join(core_dirs[:5])}...",
                layer="semantic",
                tags=["README索引", "集成完成", "directory_index"],
                priority="high"
            )
            print(f"  ✓ 存储成功")
        except Exception as e:
            print(f"  ✗ 存储失败: {e}")

    print("\n" + "=" * 60)
    print("README索引体系集成完成!")
    print("=" * 60)
    print("\n使用方法:")
    print("  1. 查看生成的README.md: 打开各核心目录")
    print("  2. 更新动态区块: integrator.update_section(dir_path, 'path_index', new_content)")
    print("  3. 启动自动更新: manager.start_auto_update(interval_seconds=300)")
    print("  4. 触发手动更新: manager.trigger_update(dir_path, 'on_change')")


if __name__ == "__main__":
    main()
