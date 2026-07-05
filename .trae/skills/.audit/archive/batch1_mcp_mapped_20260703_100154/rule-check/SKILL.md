# 规则检查 (Rule Check) — @luling (L3)

## 触发条件

- 代码变更提交
- 架构变更提案
- CI/CD流水线触发

## 执行流程

1. **规则加载**：project_rules.md + 天机修复法则 + 灵境规范
2. **变更比对**：对比新旧版本差异
3. **规则匹配**：逐条匹配规则项
4. **违规标记**：HARD_BLOCK(阻断) / SOFT_WARN(告警) / INFO(提醒)
5. **修复建议**：给出合规修复方案

## MCP 工具

- `knowledge-graph-global`: kg_query, kg_validate
- `security-scanner`: scan_file
- `command-executor`: execute_command

## 规则体系

```yaml
天机修复法则:
  - 道生一: 核心原则锚定, 违反→HARD_BLOCK
  - 一生二: 双链验证, 违反→HARD_BLOCK
  - 二生三: 三维透视, 违反→SOFT_WARN
  - 三生万物: 持续进化, 违反→INFO

灵境规范:
  - 道谱合规: 九道三十六地煞七十二天罡, 违反→HARD_BLOCK
  - 拷问驱动: 14拷问检查, 违反→SOFT_WARN
  - 三链协调: 体验链→业务链→技术链, 违反→SOFT_WARN
```

## 联动 Agent

- @zhenshan (安全) — 安全规则接入
- @wenzong (文宗) — 代码规范检查
- @zhuiguang (性能) — 性能规则接入
