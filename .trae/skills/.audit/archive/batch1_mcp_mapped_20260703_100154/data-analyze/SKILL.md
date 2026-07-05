# 数据分析 (Data Analyze) — @tiansuan

## 触发条件

- 用户请求数据分析/可视化
- 进化闭环统计报告生成
- 记忆系统容量趋势分析

## 执行流程

1. **数据采集**：从 memory-engine-global 拉取记忆统计
2. **清洗转换**：去重、归一化、时区对齐
3. **统计分析**：趋势检测、异常检测、聚类分析
4. **可视化**：生成时序图/热力图/分布图
5. **洞察报告**：automl_run → 关键发现

## MCP 工具

- `memory-engine-global`: memory_stats, memory_capacity, memory_query
- `ops-engine`: resource_monitor
- `command-executor`: execute_command

## 分析维度

```yaml
记忆维度:
  - L0感官: 写入速率, 命中率
  - L1工作: 活跃度, 衰减曲线
  - L4模式: 模式提取量, 准确率
  - L5元认知: 策略变更频率
系统维度:
  - Agent响应: P50/P99延迟
  - MCP吞吐: QPS, 错误率
  - 资源: CPU/内存/磁盘趋势
```

## 联动 Agent

- @yiku (忆库) — 记忆策略依据
- @evolver (进化) — 闭环进化数据输入
- @zhuiguang (性能) — 性能瓶颈数据
