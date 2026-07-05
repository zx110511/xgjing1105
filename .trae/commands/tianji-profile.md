---
name: tianji-profile
description: 天机性能剖析 - 深度分析函数/模块性能瓶颈
category: 天机运维
argument-hint: "<function | module>"
---

# /tianji-profile - 天机性能剖析

对指定函数或模块进行深度性能剖析。

## 剖析流程
1. 调用 `profile_function` 采集性能数据
2. 调用 `get_cpu_profile` 获取CPU热点
3. 调用 `get_memory_profile` 获取内存使用
4. 调用 `analyze_bottleneck` 分析瓶颈
5. 调用 `get_performance_metrics` 对比历史基准

## 输出
- 热点函数排行
- 内存泄漏检测
- 优化建议

## TVP声明
[TVP]#system→@zhuiguang | [OPS]#profile
