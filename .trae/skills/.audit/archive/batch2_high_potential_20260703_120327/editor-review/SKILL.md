# 编辑器审查 (Editor Review) — @wenzong (L1)

## 触发条件

- 代码/文档写入前
- 内容规范检查
- 发布前审查

## 执行流程

1. **内容读取**：获取待审查内容
2. **规范匹配**：对比编码规范/文档规范
3. **问题标记**：语法错误、风格违规、安全风险
4. **自动修复**：可自动修复的直接修正
5. **审查报告**：不可自动修复的 → 标注建议

## MCP 工具

- `memory-engine-global`: memory_query（规范查询）
- `knowledge-graph-global`: kg_validate
- `security-scanner`: scan_file

## 审查维度

```yaml
code_review:
  - Python: PEP8, type hints, docstring
  - JS/TS: ESLint, TypeScript strict
  - SQL: 注入防护, 索引优化
  - Config: JSON/YAML格式, 环境变量
doc_review:
  - Markdown: 标题层级, 链接有效
  - 中文: 统一术语, 无歧义
  - 图示: Mermaid语法
```

## 联动 Agent

- @jingwei (经纬) — 代码质量协同
- @luling (规则) — 规则合规
- @zhenshan (安全) — 安全审查
- @lingxi (对话) — 对话质量协同
