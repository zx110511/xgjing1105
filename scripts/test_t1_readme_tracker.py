r"""
T1 R-SATIS 根目录源架构追踪索引系统 测试脚本 v9.1
==================================================
测试用例: 22项 (全量功能覆盖)
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0


def test(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}  --  {detail}")


from core.shared.readme_tracker import (
    ReadmeTracker,
    ReadmeTrackerConfig,
    FileEntry,
    FolderState,
)

print("=" * 60)
print("  T1 R-SATIS 根目录源架构追踪索引系统 测试 v9.1")
print("=" * 60)

with tempfile.TemporaryDirectory() as tmpdir:
    config = ReadmeTrackerConfig(
        root_path=os.path.abspath(tmpdir),
        exclude_patterns=[".git", "node_modules", "__pycache__", ".venv"],
        summary_method="hash",
        update_interval_seconds=0,
        watchdog_enabled=False,
    )
    tracker = ReadmeTracker(config=config)

    print("\n🧭 1. 配置解析 (3项)")
    test("1.1 root_path正确", tracker._config.root_path == os.path.abspath(tmpdir))
    test("1.2 excluded=.git", ".git" in tracker._config.exclude_patterns)
    test("1.3 summary_method=hash", tracker._config.summary_method == "hash")

    subdir = os.path.join(tmpdir, "subdir")
    os.makedirs(subdir, exist_ok=True)
    with open(os.path.join(tmpdir, "test.py"), "w", encoding="utf-8") as f:
        f.write("# test file\nprint('hello')")
    with open(os.path.join(subdir, "nested.md"), "w", encoding="utf-8") as f:
        f.write("# Nested file\n")

    print("\n📁 2. 目录扫描 (4项)")
    dirs, files = tracker.scan_folder(os.path.abspath(tmpdir))
    test("2.1 扫描到至少1个文件夹", len(dirs) >= 1, f"实际{len(dirs)}")
    test("2.2 扫描到至少1个文件", len(files) >= 1, f"实际{len(files)}")
    test("2.3 不含__pycache__", "__pycache__" not in [d.name for d in dirs])
    test("2.4 文件含test.py", any(f.name == "test.py" for f in files))

    print("\n📄 3. 索引生成 (4项)")
    path_index = tracker._generate_path_index(dirs, files)
    test("3.1 含文件夹索引标题", "## 📁 文件夹索引" in path_index)
    test("3.2 含文件索引标题", "## 📄 文件索引" in path_index)
    test("3.3 含subdir/", "./subdir/" in path_index)
    test("3.4 含test.py", "./test.py" in path_index)

    print("\n🔖 4. 摘要生成 (3项)")
    for fe in files:
        if fe.name == "test.py":
            s = tracker._compute_summary(fe.name)
            test("4.1 SHA-256返回64位hex", len(s) == 64 and all(c in "0123456789abcdef" for c in s.lower()),
                 f"长度{len(s)}")
            break
    summaries = {fe.rel_path: tracker._compute_summary(fe.name) for fe in files}
    summary_table = tracker._generate_summary_table(summaries)
    test("4.2 含文件摘要标题", "## 🔖 文件摘要映射" in summary_table)
    test("4.3 摘要表含路径", "./test.py" in summary_table)

    path_index = tracker._generate_path_index(dirs, files)
    auto_block = tracker._build_auto_block(path_index, summary_table)

    print("\n📝 5. 标记区块 (3项)")
    merged = tracker._merge_content("", auto_block, "")
    test("5.1 含AUTO-START", "<!-- AUTO-START -->" in merged)
    test("5.2 含AUTO-END", "<!-- AUTO-END -->" in merged)
    test("5.3 含路径索引内容", "## 📁 文件夹索引" in merged)

    readme_path = os.path.join(tmpdir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("# 用户自定义介绍\n\n这是我的项目说明。\n")

    print("\n🔄 6. README更新 (3项)")
    result = tracker.update_readme(os.path.abspath(tmpdir))
    test("6.1 update_readme成功", result)
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    test("6.2 用户内容保留", "我的项目说明" in content)
    test("6.3 自动区块追加", "AUTO-START" in content)

    with open(os.path.join(tmpdir, "new_file.txt"), "w", encoding="utf-8") as f:
        f.write("new content\n")
    result2 = tracker.update_readme(os.path.abspath(tmpdir))
    test("6.4 增量更新检测到新文件", result2)
    with open(readme_path, "r", encoding="utf-8") as f:
        content2 = f.read()
    test("6.5 新文件入索引", "new_file.txt" in content2)

    print("\n💚 7. health+status (3项)")
    h = tracker.health()
    test("7.1 health返回dict", isinstance(h, dict))
    test("7.2 config_root_path一致", h.get("config_root_path") == tracker._config.root_path)
    s = tracker.get_status()
    test("7.3 status含folders_processed", "folders_processed" in s)

    print("\n📊 8. FolderState缓存 (2项)")
    state = tracker._get_folder_state(os.path.abspath(tmpdir))
    test("8.1 状态缓存非空", isinstance(state, FolderState))
    test("8.2 subdir标记为subfolder", state.subfolder_hashes is not None)

    print("\n" + "=" * 60)
    print(f"  结果: ✅ {PASS} / ❌ {FAIL} / 总计 {PASS + FAIL}")
    print("=" * 60)
    sys.exit(0 if FAIL == 0 else 1)