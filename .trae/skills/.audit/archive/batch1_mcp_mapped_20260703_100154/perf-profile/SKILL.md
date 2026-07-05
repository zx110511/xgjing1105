# 性能剖析 (Performance Profile) — @zhuiguang

## 触发条件

- 代码变更后自动触发
- 用户请求性能分析
- P99延迟超过1.5s

## 执行流程

1. **函数级剖析**：profile_function（热点函数识别）
2. **内存剖析**：memory_profile（内存泄漏检测）
3. **CPU剖析**：cpu_profile（CPU瓶颈定位）
4. **IO剖析**：io_profile（磁盘/网络IO瓶颈）
5. **瓶颈诊断**：bottleneck_detect
6. **优化建议**：optimization_suggest

## MCP 工具

- `performance-profiler`: profile_function, memory_profile, cpu_profile, io_profile, bottleneck_detect, optimization_suggest
- `ops-engine`: resource_monitor

## 阈值告警

```yaml
P50: >100ms → 警告
P99: >1500ms → 降级L1
Memory: >512MB → 告警
CPU: >80%持续30s → 告警
```

## 联动 Agent

- @gongzao (DevOps) — 性能瓶颈部署优化
- @qianli (运维) — 降级触发
- @tiewei (测试) — 性能回归门禁
