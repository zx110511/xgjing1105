"""灵犀·架构之眼 — 依赖扫描器测试"""

import tempfile
from pathlib import Path

import pytest

from core.lingxi.dependency_scanner import (
    ImportInfo,
    DeadCodeItem,
    ScanReport,
    scan_imports,
    build_dependency_graph,
    detect_cycles,
    find_dead_code,
    calc_coupling,
    export_dot,
    scan_and_report,
)


@pytest.fixture
def sample_project(tmp_path):
    """创建示例项目结构"""
    # main.py
    (tmp_path / "main.py").write_text(
        "from utils import helper\nfrom models import User\n\n"
        "def run():\n    helper()\n    u = User()\n", encoding="utf-8"
    )
    # utils.py
    (tmp_path / "utils.py").write_text(
        "def helper():\n    return 42\n", encoding="utf-8"
    )
    # models.py
    (tmp_path / "models.py").write_text(
        "class User:\n    pass\n", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def cycle_project(tmp_path):
    """创建循环依赖项目"""
    (tmp_path / "a.py").write_text(
        "from b import B\n\nclass A:\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "b.py").write_text(
        "from a import A\n\nclass B:\n    pass\n", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def conditional_project(tmp_path):
    """创建条件import项目"""
    (tmp_path / "optional.py").write_text(
        "try:\n    import numpy as np\nexcept ImportError:\n    np = None\n\n"
        "from core.memory.engine import ICMEEngine\n", encoding="utf-8"
    )
    return tmp_path


class TestScanImports:
    """scan_imports测试"""

    def test_empty_directory(self, tmp_path):
        """空目录扫描"""
        result = scan_imports(tmp_path)
        assert result == {}

    def test_single_file_no_imports(self, tmp_path):
        """单文件无import"""
        (tmp_path / "solo.py").write_text("x = 1\n", encoding="utf-8")
        result = scan_imports(tmp_path)
        assert "solo.py" in result
        assert len(result["solo.py"]) == 0

    def test_normal_imports(self, sample_project):
        """正常import链"""
        result = scan_imports(sample_project)
        assert "main.py" in result
        main_imports = result["main.py"]
        assert len(main_imports) == 2
        names = {imp.module_name for imp in main_imports}
        assert "utils" in names
        assert "models" in names

    def test_from_import_names(self, sample_project):
        """from...import名称解析"""
        result = scan_imports(sample_project)
        main_imports = result["main.py"]
        for imp in main_imports:
            if imp.module_name == "utils":
                assert "helper" in imp.imported_names
            elif imp.module_name == "models":
                assert "User" in imp.imported_names

    def test_conditional_import(self, conditional_project):
        """条件import检测"""
        result = scan_imports(conditional_project)
        opt_imports = result["optional.py"]
        numpy_imp = [i for i in opt_imports if i.module_name == "numpy"]
        assert len(numpy_imp) == 1
        assert numpy_imp[0].is_conditional is True
        # 非条件import
        engine_imp = [i for i in opt_imports if i.module_name == "core.engine"]
        assert len(engine_imp) == 1
        assert engine_imp[0].is_conditional is False

    def test_syntax_error_file(self, tmp_path):
        """语法错误文件处理"""
        (tmp_path / "broken.py").write_text("def broken(\n", encoding="utf-8")
        result = scan_imports(tmp_path)
        assert "broken.py" in result
        assert len(result["broken.py"]) == 0


class TestBuildDependencyGraph:
    """build_dependency_graph测试"""

    def test_simple_graph(self, sample_project):
        """简单依赖图"""
        imports = scan_imports(sample_project)
        graph = build_dependency_graph(imports)
        assert "main" in graph
        assert "utils" in graph["main"] or "models" in graph["main"]

    def test_with_base_package(self, tmp_path):
        """带base_package过滤"""
        (tmp_path / "app.py").write_text(
            "from core.memory.engine import ICMEEngine\nimport os\nfrom pathlib import Path\n",
            encoding="utf-8",
        )
        imports = scan_imports(tmp_path)
        graph = build_dependency_graph(imports, base_package="core")
        # os和pathlib应被过滤
        if "app" in graph:
            assert "os" not in graph["app"]
            assert "pathlib" not in graph["app"]

    def test_empty_imports(self):
        """空import映射"""
        graph = build_dependency_graph({})
        assert graph == {}


class TestDetectCycles:
    """detect_cycles测试"""

    def test_no_cycles(self, sample_project):
        """无循环依赖"""
        imports = scan_imports(sample_project)
        graph = build_dependency_graph(imports)
        cycles = detect_cycles(graph)
        assert len(cycles) == 0

    def test_simple_cycle(self, cycle_project):
        """简单循环依赖"""
        imports = scan_imports(cycle_project)
        graph = build_dependency_graph(imports)
        cycles = detect_cycles(graph)
        assert len(cycles) >= 1

    def test_empty_graph(self):
        """空图"""
        cycles = detect_cycles({})
        assert len(cycles) == 0

    def test_self_cycle(self):
        """自循环"""
        graph = {"a": {"a"}}
        cycles = detect_cycles(graph)
        assert len(cycles) >= 1

    def test_three_node_cycle(self):
        """三节点循环"""
        graph = {"a": {"b"}, "b": {"c"}, "c": {"a"}}
        cycles = detect_cycles(graph)
        assert len(cycles) >= 1


class TestFindDeadCode:
    """find_dead_code测试"""

    def test_no_dead_code(self, tmp_path):
        """无死代码"""
        (tmp_path / "used.py").write_text(
            "def add(a, b):\n    return a + b\n\nresult = add(1, 2)\n",
            encoding="utf-8",
        )
        dead = find_dead_code(tmp_path)
        # add被引用了
        add_items = [d for d in dead if d.name == "add"]
        assert len(add_items) == 0

    def test_dead_function(self, tmp_path):
        """死函数"""
        (tmp_path / "dead.py").write_text(
            "def never_called():\n    pass\n",
            encoding="utf-8",
        )
        dead = find_dead_code(tmp_path)
        names = {d.name for d in dead}
        assert "never_called" in names

    def test_dead_class(self, tmp_path):
        """死类"""
        (tmp_path / "dead_class.py").write_text(
            "class UnusedClass:\n    pass\n",
            encoding="utf-8",
        )
        dead = find_dead_code(tmp_path)
        names = {d.name for d in dead}
        assert "UnusedClass" in names

    def test_private_methods_skipped(self, tmp_path):
        """私有方法跳过"""
        (tmp_path / "private.py").write_text(
            "def _private_helper():\n    pass\n",
            encoding="utf-8",
        )
        dead = find_dead_code(tmp_path)
        names = {d.name for d in dead}
        assert "_private_helper" not in names

    def test_empty_directory(self, tmp_path):
        """空目录"""
        dead = find_dead_code(tmp_path)
        assert dead == []


class TestCalcCoupling:
    """calc_coupling测试"""

    def test_simple_coupling(self):
        """简单耦合度"""
        graph = {"a": {"b", "c"}, "b": {"c"}, "c": set()}
        coupling = calc_coupling(graph)
        assert "a" in coupling
        assert "b" in coupling
        assert coupling["a"] > coupling["b"]

    def test_no_dependencies(self):
        """无依赖"""
        graph = {"a": set()}
        coupling = calc_coupling(graph)
        assert coupling["a"] == 0.0

    def test_empty_graph(self):
        """空图"""
        coupling = calc_coupling({})
        assert coupling == {}


class TestExportDot:
    """export_dot测试"""

    def test_export_simple(self, tmp_path):
        """简单DOT导出"""
        graph = {"a": {"b"}, "b": {"c"}}
        output = tmp_path / "deps.dot"
        export_dot(graph, output)
        content = output.read_text(encoding="utf-8")
        assert "digraph" in content
        assert "a -> b" in content
        assert "b -> c" in content

    def test_export_empty(self, tmp_path):
        """空图导出"""
        graph: dict = {}
        output = tmp_path / "empty.dot"
        export_dot(graph, output)
        content = output.read_text(encoding="utf-8")
        assert "digraph" in content


class TestScanAndReport:
    """scan_and_report集成测试"""

    def test_full_report(self, sample_project):
        """完整报告"""
        report = scan_and_report(sample_project)
        assert isinstance(report, ScanReport)
        assert report.total_files >= 3
        assert report.total_imports >= 2
        assert report.total_functions >= 1
        assert report.total_classes >= 1

    def test_report_with_cycles(self, cycle_project):
        """循环依赖报告"""
        report = scan_and_report(cycle_project)
        assert len(report.cycles) >= 1

    def test_core_directory_scan(self):
        """core/目录实际扫描"""
        core_dir = Path("core")
        if not core_dir.exists():
            pytest.skip("core/目录不存在")
        report = scan_and_report(core_dir, base_package="core")
        assert report.total_files > 0
        assert report.total_functions > 0
        assert report.total_classes > 0
        # 验证报告结构完整
        assert isinstance(report.cycles, list)
        assert isinstance(report.dead_code, list)
        assert isinstance(report.coupling, dict)
