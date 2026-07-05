---
name: tianji-commit
description: 天机规范Git提交 - 自动生成Conventional Commits消息
category: 天机开发
argument-hint: "[commit-message-hint]"
---

# /tianji-commit - 天机规范提交

自动分析代码变更并生成符合 Conventional Commits 规范的提交消息。

## 执行步骤
1. 检查当前git状态和变更文件
2. 调用天机记忆检索相关上下文
3. 按 `类型(范围): 描述` 格式生成commit message
4. 符合天机宪法v6.0编码规范要求

## 输出格式
```
<type>(<scope>): <description>

<body>
```

支持类型: feat/fix/docs/style/refactor/perf/test/chore
