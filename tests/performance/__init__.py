# -*- coding: utf-8-sig -*-
"""天机v10.0.1 性能基准测试包 (P5-2)  [v10-ready]

使用 pytest-benchmark 建立 MemoryCore / 存储后端 / 搜索的性能基线。
若环境未安装 pytest-benchmark，conftest.py 提供基于 time.perf_counter 的
等价回退 fixture，保证基准测试在任意环境均可运行并记录基线。

目标指标 (仅记录基线，不硬断数值):
    - 单条写入       < 100ms
    - 单条读取       < 50ms
    - 搜索(20结果)   < 200ms
    - 批量写入(100条) < 2s
"""
