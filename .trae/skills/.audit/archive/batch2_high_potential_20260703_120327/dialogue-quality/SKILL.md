# 对话质量检查 (Dialogue Quality) — @lingxi

## 触发条件

- 每次用户对话后
- 对话历史审计
- Agent输出质量评估

## 执行流程

1. **对话捕获**：trae_capture → 完整对话上下文
2. **质量评分**：多维度量化评估
3. **问题标记**：幻觉、遗漏、歧义、冗余
4. **反馈闭环**：质量低 → L5元认知调整策略
5. **改进建议**：给对应Agent的优化方向

## MCP 工具

- `memory-engine-global`: memory_query
- `knowledge-graph-global`: kg_query, kg_validate
- `agent-framework-global`: agent_capability

## 评估维度

```yaml
accuracy: # 准确性
  - 事实正确率
  - 代码可运行率
  - MCP调用正确率
completeness: # 完整性
  - 任务覆盖率
  - 边界条件考虑
efficiency: # 效率
  - 工具调用次数
  - 对话轮次
safety: # 安全性
  - 无敏感信息泄露
  - 无危险操作
```

## 联动 Agent

- @wenzong (文宗) — 内容审查协同
- @inshu (因树) — 知识验证
- @evolver (进化) — 质量反馈输入
