\""\""\""Trae测试工作区 - Python单元测试\""\""\""

import pytest
from src.calculator import Calculator, greet, fibonacci


class TestCalculator:
    \""\""\""Calculator类测试\""\""\"""
    
    @pytest.fixture
    def calc(self) -> Calculator:
        return Calculator()
    
    def test_add(self, calc: Calculator) -> None:
        assert calc.add(2, 3) == 5
        assert calc.add(-1, 1) == 0
        assert calc.add(0, 0) == 0
    
    def test_subtract(self, calc: Calculator) -> None:
        assert calc.subtract(5, 3) == 2
        assert calc.subtract(1, 1) == 0
        assert calc.subtract(0, 5) == -5
    
    def test_multiply(self, calc: Calculator) -> None:
        assert calc.multiply(2, 3) == 6
        assert calc.multiply(-2, 3) == -6
        assert calc.multiply(0, 100) == 0
    
    def test_divide(self, calc: Calculator) -> None:
        assert calc.divide(6, 2) == 3.0
        assert calc.divide(5, 2) == 2.5
        assert calc.divide(0, 5) == 0.0
    
    def test_divide_by_zero(self, calc: Calculator) -> None:
        with pytest.raises(ValueError):
            calc.divide(1, 0)
    
    def test_history(self, calc: Calculator) -> None:
        calc.add(1, 2)
        calc.multiply(3, 4)
        history = calc.get_history()
        assert len(history) == 2
        assert history[0][\""operation\""] == \""add\""
        assert history[1][\""operation\""] == \""multiply\""


class TestGreet:
    \""\""\""greet函数测试\""\""\"""
    
    def test_greet_default(self) -> None:
        result = greet(""Trae"")
        assert ""Trae"" in result
        assert ""Hello"" in result
    
    def test_greet_custom(self) -> None:
        result = greet(""Python"")
        assert ""Python"" in result


class TestFibonacci:
    \""\""\""fibonacci函数测试\""\""\"""
    
    def test_fibonacci_zero(self) -> None:
        assert fibonacci(0) == 0
    
    def test_fibonacci_one(self) -> None:
        assert fibonacci(1) == 1
    
    def test_fibonacci_sequence(self) -> None:
        expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
        for i, value in enumerate(expected):
            assert fibonacci(i) == value


@pytest.mark.integration
class TestIntegration:
    \""\""\""集成测试\""\""\"""
    
    def test_calculator_workflow(self) -> None:
        calc = Calculator()
        result1 = calc.add(10, 20)
        result2 = calc.multiply(result1, 2)
        result3 = calc.subtract(result2, 10)
        assert result3 == 50
