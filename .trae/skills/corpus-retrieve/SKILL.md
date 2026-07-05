# 语料检索 (corpus/retrieve)

## 目的
从语料库中检索特定类型和风格的语料元素，支持语义匹配和精准过滤

## 触发场景
- 用户需要查找特定类型的语料素材
- 创作时需要参考已有风格或设定
- 需要按类别筛选高质量语料

## 执行步骤
### Step 1: 解析查询意图
1. 分析用户query的关键词和语义
2. 识别检索目标(人物/世界观/情节/风格/情感/对话/机制)
3. 确定匹配策略(精确匹配/模糊匹配/语义相似)

### Step 2: 执行检索
1. 调用memory_recall或本地语料索引
2. 应用category/subcategory过滤
3. 按min_quality阈值过滤低质量条目
4. 限制返回数量(limit参数)

### Step 3: 结果整理
1. 按相关度排序返回结果
2. 标注每个结果的来源和质量分
3. 提供摘要统计信息

## 参数说明
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | ✅ | - | 检索查询词 |
| category | string | ❌ | all | 类别: character/world/plot/style/emotion/dialogue/mechanics |
| subcategory | string | ❌ | - | 子类别限定 |
| limit | integer | ❌ | 20 | 返回数量上限 |
| min_quality | number | ❌ | 0.6 | 最低质量分(0-1) |

## 输出格式
```json
{
  "retrieve_id": "ret-{timestamp}",
  "query": "{original_query}",
  "total_found": N,
  "returned": N,
  "results": [
    {
      "id": "corp-{id}",
      "type": "{category}",
      "content_preview": "...",
      "quality_score": 0.85,
      "source": "{file_ref}",
      "tags": ["tag1", "tag2"]
    }
  ],
  "statistics": {
    "by_category": {},
    "avg_quality": 0.78,
    "top_categories": []
  }
}
```

## 绑定Agent
@analyzer

## 协作伙伴
@corpus-miner | @writer | @planner

## 质量标准
- 检索准确率 >= 80%
- 返回结果质量分 >= min_quality
- 响应时间 < 10s
