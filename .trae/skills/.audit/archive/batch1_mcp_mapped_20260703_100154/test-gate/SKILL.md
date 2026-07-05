# 测试门禁 (Test Gate) — @tiewei

## 触发条件

- 代码变更提交后自动触发
- 用户请求运行测试
- 发布前质量检查

## 执行流程

1. **Stage-Gate 校验**：SG-0(环境) → SG-1(类型) → SG-2(功能) → SG-3(MCP集成) → SG-4(回归)
2. **测试执行**：pytest --strict-markers -x
3. **覆盖率检查**：≥80% 通过
4. **性能退化检测**：<5% 退化方可放行

## MCP 工具

- `command-executor`: execute_command, command_status
- `security-scanner`: scan_file, vulnerability_report
- `performance-profiler`: bottleneck_detect

## 输出格式

```json
{
  "stage": "SG-0..SG-4",
  "tests_total": N,
  "tests_passed": N,
  "coverage": "85%",
  "performance_delta": "+2%",
  "verdict": "PASS|BLOCK",
  "issues": []
}
```

## 联动 Agent

- @qianli (运维) — 部署前确认
- @zhenshan (安全) — 安全扫描通过
- @zhuiguang (性能) — 性能无退化
