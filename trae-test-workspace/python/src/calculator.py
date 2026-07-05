\""\""\""Trae测试工作区 - Python示例模块\""\""\""

from typing import List, Dict, Any


class Calculator:
    \""\""\""简单计算器类，用于测试Trae功能\""\""\"""
    
    def __init__(self) -> None:
        self.history: List[Dict[str, Any]] = []
    
    def add(self, a: int, b: int) -> int:
        \""\""\""加法\""\""\"""
        result = a + b
        self.history.append({\""operation"": \""add\"", \""a"": a, \""b"": b, \""result"": result})
        return result
    
    def subtract(self, a: int, b: int) -> int:
        \""\""\""减法\""\""\"""
        result = a - b
        self.history.append({\""operation"": \""subtract\"", \""a"": a, \""b"": b, \""result"": result})
        return result
    
    def multiply(self, a: int, b: int) -> int:
        \""\""\""乘法\""\""\"""
        result = a * b
        self.history.append({\""operation"": \""multiply\"", \""a"": a, \""b"": b, \""result"": result})
        return result
    
    def divide(self, a: int, b: int) -> float:
        \""\""\""除法\""\""\"""
        if b == 0:
            raise ValueError(""Cannot divide by zero"")
        result = a / b
        self.history.append({\""operation"": \""divide\"", \""a"": a, \""b"": b, \""result"": result})
        return result
    
    def get_history(self) -> List[Dict[str, Any]]:
        \""\""\""获取操作历史\""\""\"""
        return self.history


def greet(name: str) -> str:
    \""\""\""问候函数\""\""\"""
    return f\""Hello, {name}! Welcome to Trae test workspace.\""


def fibonacci(n: int) -> int:
    \""\""\""斐波那契数列\""\""\"""
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fibonacci(n - 1) + fibonacci(n - 2)
