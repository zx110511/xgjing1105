---
name: tianji-review
description: 天机代码审查 - 多维度代码质量与安全检查
category: 天机开发
argument-hint: "<file-pattern>"
---

# /tianji-review - 天机代码审查

对指定代码执行多维度审查。

## 审查维度
1. **宪法合规**: 调用 `rule_evaluate` 检查天机宪法合规性
2. **代码质量**: 圈复杂度/命名规范/类型注解
3. **安全扫描**: 调用 `scan_vulnerabilities` 检测漏洞
4. **架构一致**: 检查道域划分和模块边界
5. **记忆对齐**: 检查操作是否记录到ICME六层

## 输出
生成审查报告，按风险等级排序

## TVP声明
[TVP]#system→@mingjing | [OPS]#code_review
