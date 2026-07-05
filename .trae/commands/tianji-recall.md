---
name: tianji-recall
description: 天机记忆智能召回查询
category: 天机记忆
---

# /tianji-recall - 天机记忆召回

从ICME六层记忆系统中召回相关记忆。

## 输入参数
- `query` (必填): 查询关键词
- `layer` (可选): 目标层级 (sensory/working/short_term/episodic/semantic/meta)，默认按优先级搜索
- `limit` (可选): 返回条数，默认5

## 执行步骤
1. 调用 `memory_recall` 检索匹配记忆
2. 调用 `tianji_expand_query` 扩展查询维度
3. 调用 `tianji_semantic_search` 深度语义搜索
4. 汇总结果并格式化输出

## 输出格式
```json
{
  "query": "...",
  "results": [...],
  "layers_hit": {...},
  "total_hits": N
}
```

## TVP声明
[TVP]#system→@yiku | [OPS]#memory_recall
