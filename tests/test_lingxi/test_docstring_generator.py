"""灵犀·自愈之手 — Docstring生成器测试"""

import tempfile
from pathlib import Path

import pytest

from core.lingxi.docstring_generator import (
    MissingDoc,
    FuncSignature,
    DocstringReport,
    scan_missing_docstrings,
    parse_function_signature,
    generate_docstring,
    insert_docstring,
    verify_syntax,
    process_file,
    process_directory,
)


@pytest.fixture
def sample_file(tmp_path):
    """创建含缺失docstring的示例文件"""
    code = '''"""模块docstring"""

def add(a, b):
    return a + b

def subtract(x: int, y: int) -> int:
    """减法运算"""
    return x - y

class Calculator:
    def multiply(self, a, b):
        return a * b

    def divide(self, a: float, b: float) -> float:
        """除法运算"""
        return a / b

async def fetch_data(url: str) -> dict:
    pass

def _private_func():
    pass

@property
def value(self):
    return 42
'''
    f = tmp_path / "sample.py"
    f.write_text(code, encoding="utf-8")
    return f


@pytest.fixture
def no_docstring_file(tmp_path):
    """创建无任何docstring的文件"""
    code = "def hello():\n    pass\n\nclass World:\n    pass\n"
    f = tmp_path / "no_doc.py"
    f.write_text(code, encoding="utf-8")
    return f


class TestScanMissingDocstrings:
    """scan_missing_docstrings测试"""

    def test_scan_finds_missing(self, sample_file):
        """扫描发现缺失docstring"""
        missing = scan_missing_docstrings(sample_file)
        names = {m.name for m in missing}
        assert "add" in names  # 无docstring
        assert "multiply" in names  # 方法无docstring
        assert "fetch_data" in names  # async无docstring
        assert "value" in names  # property无docstring

    def test_scan_skips_with_docstring(self, sample_file):
        """跳过已有docstring的函数"""
        missing = scan_missing_docstrings(sample_file)
        names = {m.name for m in missing}
        assert "subtract" not in names  # 有docstring
        assert "divide" not in names  # 有docstring

    def test_scan_class(self, no_docstring_file):
        """扫描类"""
        missing = scan_missing_docstrings(no_docstring_file)
        names = {m.name for m in missing}
        assert "World" in names

    def test_scan_kind(self, sample_file):
        """正确识别kind"""
        missing = scan_missing_docstrings(sample_file)
        by_name = {m.name: m for m in missing}
        assert by_name["add"].kind == "function"
        assert by_name["fetch_data"].kind == "async_function"
        assert by_name["multiply"].kind == "function"

    def test_scan_is_method(self, sample_file):
        """正确识别方法"""
        missing = scan_missing_docstrings(sample_file)
        by_name = {m.name: m for m in missing}
        assert by_name["multiply"].is_method is True
        assert by_name["add"].is_method is False

    def test_scan_syntax_error(self, tmp_path):
        """语法错误文件"""
        f = tmp_path / "broken.py"
        f.write_text("def broken(\n", encoding="utf-8")
        missing = scan_missing_docstrings(f)
        assert missing == []

    def test_scan_empty_file(self, tmp_path):
        """空文件"""
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        missing = scan_missing_docstrings(f)
        assert missing == []


class TestParseFunctionSignature:
    """parse_function_signature测试"""

    def test_simple_signature(self):
        """简单签名"""
        import ast
        tree = ast.parse("def foo(a, b): pass")
        func = tree.body[0]
        sig = parse_function_signature(func)
        assert sig.name == "foo"
        assert len(sig.params) == 2
        assert sig.return_type is None

    def test_typed_signature(self):
        """带类型注解签名"""
        import ast
        tree = ast.parse("def foo(a: int, b: str) -> bool: pass")
        func = tree.body[0]
        sig = parse_function_signature(func)
        assert sig.params[0] == ("a", "int", None)
        assert sig.params[1] == ("b", "str", None)
        assert sig.return_type == "bool"

    def test_async_signature(self):
        """async函数签名"""
        import ast
        tree = ast.parse("async def fetch(url: str) -> dict: pass")
        func = tree.body[0]
        sig = parse_function_signature(func)
        assert sig.is_async is True
        assert sig.return_type == "dict"

    def test_method_signature(self):
        """方法签名(含self)"""
        import ast
        tree = ast.parse("class C:\n    def method(self, x): pass")
        cls = tree.body[0]
        func = cls.body[0]
        sig = parse_function_signature(func)
        assert sig.is_method is True


class TestGenerateDocstring:
    """generate_docstring测试"""

    def test_function_docstring(self):
        """函数docstring"""
        m = MissingDoc(name="add", kind="function", line=1, end_line=2, args=["a", "b"])
        doc = generate_docstring(m)
        assert "add" in doc
        assert "Args:" in doc
        assert "a" in doc
        assert "b" in doc

    def test_async_docstring(self):
        """async函数docstring"""
        m = MissingDoc(name="fetch", kind="async_function", line=1, end_line=2, args=["url"])
        doc = generate_docstring(m)
        assert "异步" in doc

    def test_class_docstring(self):
        """类docstring"""
        m = MissingDoc(name="Calculator", kind="class", line=1, end_line=5)
        doc = generate_docstring(m)
        assert "Calculator" in doc

    def test_with_return_type(self):
        """带返回类型"""
        m = MissingDoc(name="calc", kind="function", line=1, end_line=2, args=["x"], returns="int")
        doc = generate_docstring(m)
        assert "Returns:" in doc
        assert "int" in doc

    def test_no_args(self):
        """无参数函数"""
        m = MissingDoc(name="run", kind="function", line=1, end_line=2, args=[])
        doc = generate_docstring(m)
        assert "Args:" not in doc


class TestInsertDocstring:
    """insert_docstring测试"""

    def test_insert_simple(self, tmp_path):
        """简单插入"""
        f = tmp_path / "test.py"
        f.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        result = insert_docstring(f, "add", "加法运算。", 1)
        assert result is True
        content = f.read_text(encoding="utf-8-sig")
        assert '"""' in content
        assert "加法运算" in content

    def test_insert_preserves_syntax(self, tmp_path):
        """插入后语法正确"""
        f = tmp_path / "test.py"
        f.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        insert_docstring(f, "add", "加法。", 1)
        assert verify_syntax(f) is True

    def test_insert_skips_existing(self, tmp_path):
        """跳过已有docstring"""
        f = tmp_path / "test.py"
        f.write_text('def add(a, b):\n    """已有"""\n    return a + b\n', encoding="utf-8")
        result = insert_docstring(f, "add", "新的", 1)
        assert result is False

    def test_insert_invalid_line(self, tmp_path):
        """无效行号"""
        f = tmp_path / "test.py"
        f.write_text("x = 1\n", encoding="utf-8")
        result = insert_docstring(f, "foo", "test", 999)
        assert result is False


class TestVerifySyntax:
    """verify_syntax测试"""

    def test_valid_syntax(self, tmp_path):
        """有效语法"""
        f = tmp_path / "valid.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert verify_syntax(f) is True

    def test_invalid_syntax(self, tmp_path):
        """无效语法"""
        f = tmp_path / "invalid.py"
        f.write_text("def broken(\n", encoding="utf-8")
        assert verify_syntax(f) is False


class TestProcessFile:
    """process_file测试"""

    def test_dry_run(self, no_docstring_file):
        """dry_run模式不修改文件"""
        original = no_docstring_file.read_text(encoding="utf-8")
        result = process_file(no_docstring_file, dry_run=True)
        assert result["dry_run"] is True
        assert len(result["missing"]) > 0
        # 文件未被修改
        assert no_docstring_file.read_text(encoding="utf-8") == original

    def test_actual_insert(self, no_docstring_file):
        """实际插入"""
        result = process_file(no_docstring_file, dry_run=False)
        assert len(result["generated"]) > 0
        # 文件被修改
        content = no_docstring_file.read_text(encoding="utf-8-sig")
        assert '"""' in content

    def test_file_with_existing_docstring(self, tmp_path):
        """已有docstring的文件"""
        f = tmp_path / "docced.py"
        f.write_text('def foo():\n    """已有"""\n    pass\n', encoding="utf-8")
        result = process_file(f, dry_run=False)
        assert len(result["missing"]) == 0


class TestProcessDirectory:
    """process_directory测试"""

    def test_dry_run_directory(self, tmp_path):
        """目录dry_run"""
        (tmp_path / "a.py").write_text("def foo():\n    pass\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("def bar():\n    pass\n", encoding="utf-8")
        report = process_directory(tmp_path, dry_run=True)
        assert isinstance(report, DocstringReport)
        assert report.total_scanned >= 2
        assert report.missing_count >= 2
        assert report.skipped_count >= 2

    def test_empty_directory(self, tmp_path):
        """空目录"""
        report = process_directory(tmp_path, dry_run=True)
        assert report.total_scanned == 0
        assert report.missing_count == 0

    def test_actual_insert_directory(self, tmp_path):
        """目录实际插入"""
        (tmp_path / "c.py").write_text("def baz():\n    pass\n", encoding="utf-8")
        report = process_directory(tmp_path, dry_run=False)
        assert report.generated_count >= 1
