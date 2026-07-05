"""灵犀·类型注解器测试"""

import tempfile
from pathlib import Path

import pytest

from core.lingxi.type_annotator import (
    MissingAnnotation,
    AnnotationReport,
    scan_missing_annotations,
    infer_param_type,
    infer_return_type,
    insert_annotation,
    verify_syntax,
    process_file,
    process_directory,
)


@pytest.fixture
def typed_file(tmp_path):
    """已完全注解的文件"""
    code = "def add(a: int, b: int) -> int:\n    return a + b\n"
    f = tmp_path / "typed.py"
    f.write_text(code, encoding="utf-8")
    return f


@pytest.fixture
def untyped_file(tmp_path):
    """未注解的文件"""
    code = (
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "def greet(name):\n"
        "    return f'Hello {name}'\n"
        "\n"
        "def no_return():\n"
        "    pass\n"
        "\n"
        "class Calculator:\n"
        "    def multiply(self, x, y):\n"
        "        return x * y\n"
    )
    f = tmp_path / "untyped.py"
    f.write_text(code, encoding="utf-8")
    return f


class TestScanMissingAnnotations:
    """scan_missing_annotations测试"""

    def test_finds_untyped(self, untyped_file):
        """发现未注解函数"""
        missing = scan_missing_annotations(untyped_file)
        names = {m.func_name for m in missing}
        assert "add" in names
        assert "greet" in names
        assert "no_return" in names
        assert "multiply" in names

    def test_skips_typed(self, typed_file):
        """跳过已注解函数"""
        missing = scan_missing_annotations(typed_file)
        assert len(missing) == 0

    def test_untyped_params(self, untyped_file):
        """未注解参数列表"""
        missing = scan_missing_annotations(untyped_file)
        by_name = {m.func_name: m for m in missing}
        assert "a" in by_name["add"].untyped_params
        assert "b" in by_name["add"].untyped_params

    def test_missing_return(self, untyped_file):
        """缺失返回类型"""
        missing = scan_missing_annotations(untyped_file)
        by_name = {m.func_name: m for m in missing}
        assert by_name["add"].missing_return is True

    def test_is_method(self, untyped_file):
        """方法识别"""
        missing = scan_missing_annotations(untyped_file)
        by_name = {m.func_name: m for m in missing}
        assert by_name["multiply"].is_method is True
        assert by_name["add"].is_method is False

    def test_self_not_untyped(self, untyped_file):
        """self参数不计入untyped"""
        missing = scan_missing_annotations(untyped_file)
        by_name = {m.func_name: m for m in missing}
        assert "self" not in by_name["multiply"].untyped_params

    def test_syntax_error(self, tmp_path):
        """语法错误文件"""
        f = tmp_path / "broken.py"
        f.write_text("def broken(\n", encoding="utf-8")
        missing = scan_missing_annotations(f)
        assert missing == []


class TestInferParamType:
    """infer_param_type测试"""

    def test_string_method(self):
        """字符串方法推断"""
        import ast
        tree = ast.parse("def foo(x):\n    x.startswith('hello')\n")
        func = tree.body[0]
        result = infer_param_type(func, "x")
        assert result == "str"

    def test_list_method(self):
        """列表方法推断"""
        import ast
        tree = ast.parse("def foo(x):\n    x.append(1)\n")
        func = tree.body[0]
        result = infer_param_type(func, "x")
        assert result == "list"

    def test_dict_method(self):
        """字典方法推断"""
        import ast
        tree = ast.parse("def foo(x):\n    x.get('key')\n")
        func = tree.body[0]
        result = infer_param_type(func, "x")
        assert result == "dict"

    def test_arithmetic(self):
        """算术运算推断"""
        import ast
        tree = ast.parse("def foo(x):\n    return x + 1\n")
        func = tree.body[0]
        result = infer_param_type(func, "x")
        assert result == "int"

    def test_len_call(self):
        """len()调用推断"""
        import ast
        tree = ast.parse("def foo(x):\n    return len(x)\n")
        func = tree.body[0]
        result = infer_param_type(func, "x")
        assert result == "list"

    def test_fstring(self):
        """f-string推断"""
        import ast
        tree = ast.parse("def foo(x):\n    return f'value: {x}'\n")
        func = tree.body[0]
        result = infer_param_type(func, "x")
        assert result == "str"

    def test_unknown(self):
        """无法推断"""
        import ast
        tree = ast.parse("def foo(x):\n    pass\n")
        func = tree.body[0]
        result = infer_param_type(func, "x")
        assert result is None


class TestInferReturnType:
    """infer_return_type测试"""

    def test_return_int(self):
        """返回int"""
        import ast
        tree = ast.parse("def foo():\n    return 42\n")
        func = tree.body[0]
        result = infer_return_type(func)
        assert result == "int"

    def test_return_str(self):
        """返回str"""
        import ast
        tree = ast.parse("def foo():\n    return 'hello'\n")
        func = tree.body[0]
        result = infer_return_type(func)
        assert result == "str"

    def test_return_none(self):
        """返回None"""
        import ast
        tree = ast.parse("def foo():\n    pass\n")
        func = tree.body[0]
        result = infer_return_type(func)
        assert result == "None"

    def test_return_list(self):
        """返回list"""
        import ast
        tree = ast.parse("def foo():\n    return [1, 2, 3]\n")
        func = tree.body[0]
        result = infer_return_type(func)
        assert result == "list"

    def test_return_dict(self):
        """返回dict"""
        import ast
        tree = ast.parse("def foo():\n    return {'key': 'value'}\n")
        func = tree.body[0]
        result = infer_return_type(func)
        assert result == "dict"

    def test_return_bool(self):
        """返回bool"""
        import ast
        tree = ast.parse("def foo():\n    return True\n")
        func = tree.body[0]
        result = infer_return_type(func)
        assert result == "bool"

    def test_return_float(self):
        """返回float"""
        import ast
        tree = ast.parse("def foo():\n    return 3.14\n")
        func = tree.body[0]
        result = infer_return_type(func)
        assert result == "float"

    def test_return_constructor(self):
        """返回构造器调用"""
        import ast
        tree = ast.parse("def foo():\n    return str(x)\n")
        func = tree.body[0]
        result = infer_return_type(func)
        assert result == "str"


class TestInsertAnnotation:
    """insert_annotation测试"""

    def test_insert_param_type(self, tmp_path):
        """插入参数类型"""
        f = tmp_path / "test.py"
        f.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        result = insert_annotation(f, "add", {"a": "int", "b": "int"})
        assert result is True
        content = f.read_text(encoding="utf-8-sig")
        assert "a: int" in content
        assert "b: int" in content

    def test_insert_return_type(self, tmp_path):
        """插入返回类型"""
        f = tmp_path / "test.py"
        f.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        result = insert_annotation(f, "add", {}, return_type="int")
        assert result is True
        content = f.read_text(encoding="utf-8-sig")
        assert "-> int" in content

    def test_insert_both(self, tmp_path):
        """同时插入参数和返回类型"""
        f = tmp_path / "test.py"
        f.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        result = insert_annotation(f, "add", {"a": "int", "b": "int"}, return_type="int")
        assert result is True
        content = f.read_text(encoding="utf-8-sig")
        assert "a: int" in content
        assert "-> int" in content

    def test_insert_with_default(self, tmp_path):
        """带默认值的参数"""
        f = tmp_path / "test.py"
        f.write_text("def foo(x=10):\n    return x\n", encoding="utf-8")
        result = insert_annotation(f, "foo", {"x": "int"}, return_type="int")
        assert result is True
        content = f.read_text(encoding="utf-8-sig")
        assert "x: int = 10" in content

    def test_insert_preserves_self(self, tmp_path):
        """保留self参数"""
        f = tmp_path / "test.py"
        f.write_text("class C:\n    def method(self, x):\n        return x\n", encoding="utf-8")
        result = insert_annotation(f, "method", {"x": "int"}, return_type="int")
        assert result is True
        content = f.read_text(encoding="utf-8-sig")
        assert "self" in content
        assert "x: int" in content

    def test_insert_not_found(self, tmp_path):
        """函数不存在"""
        f = tmp_path / "test.py"
        f.write_text("x = 1\n", encoding="utf-8")
        result = insert_annotation(f, "nonexistent", {"x": "int"})
        assert result is False


class TestVerifySyntax:
    """verify_syntax测试"""

    def test_valid(self, tmp_path):
        """有效语法"""
        f = tmp_path / "valid.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert verify_syntax(f) is True

    def test_invalid(self, tmp_path):
        """无效语法"""
        f = tmp_path / "invalid.py"
        f.write_text("def broken(\n", encoding="utf-8")
        assert verify_syntax(f) is False


class TestProcessFile:
    """process_file测试"""

    def test_dry_run(self, untyped_file):
        """dry_run模式"""
        original = untyped_file.read_text(encoding="utf-8")
        result = process_file(untyped_file, dry_run=True)
        assert result["dry_run"] is True
        assert len(result["missing"]) > 0
        assert untyped_file.read_text(encoding="utf-8") == original

    def test_actual_insert(self, tmp_path):
        """实际插入"""
        f = tmp_path / "simple.py"
        f.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        result = process_file(f, dry_run=False)
        assert len(result["generated"]) > 0

    def test_typed_file(self, typed_file):
        """已注解文件"""
        result = process_file(typed_file, dry_run=False)
        assert len(result["missing"]) == 0


class TestProcessDirectory:
    """process_directory测试"""

    def test_dry_run(self, tmp_path):
        """目录dry_run"""
        (tmp_path / "a.py").write_text("def foo(x):\n    return x\n", encoding="utf-8")
        report = process_directory(tmp_path, dry_run=True)
        assert isinstance(report, AnnotationReport)
        assert report.total_scanned >= 1
        assert report.missing_count >= 1

    def test_empty_directory(self, tmp_path):
        """空目录"""
        report = process_directory(tmp_path, dry_run=True)
        assert report.total_scanned == 0

    def test_actual_insert(self, tmp_path):
        """目录实际插入"""
        (tmp_path / "b.py").write_text("def bar(x):\n    return x + 1\n", encoding="utf-8")
        report = process_directory(tmp_path, dry_run=False)
        assert report.generated_count >= 1
