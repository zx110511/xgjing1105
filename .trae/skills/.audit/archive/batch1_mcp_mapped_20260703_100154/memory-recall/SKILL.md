# 记忆检索 (memory/recall)

## 目的
从ICME六层记忆系统中跨层语义搜索已存储的信息。

## 触发场景
- Agent需要查询历史信息时
- 用户要求"查找"、"搜索"、"回忆"相关内容
- 创作前加载上下文/设定/角色卡时

## 执行步骤

### Step 1: 构建查询
1. **明确查询目标**
   - 具体关键词 (如 "林远", "第15章")
   - 语义描述 (如 "最近的创作记录", "世界观设定")
   - 时间范围 (如 "本周", "上次对话")

2. **选择搜索层级** (可选优化)
   - `sensory` - 原始输入
   - `working` - 当前会话
   - `short_term` - 近期决策
   - `episodic` - 事件经历
   - `semantic` - 知识概念
   - `meta` - 系统策略

### Step 2: 执行检索
```
工具: memory_recall
参数:
{
  "query": "{constructed_query}",
  "layers": ["optional_layer_list"],
  "limit": 10  // 默认返回数量
}
```

### Step 3: 结果过滤与排序
1. 检查 `relevance_score` 过滤低相关结果
2. 按时间戳或相关性排序
3. 提取关键信息片段
4. 标记来源层和entry_id

### Step 4: 结果整合
- 去重合并相似条目
- 构建结构化摘要
- 标注置信度
- 记录未找到的信息(便于后续补充)

## 参数说明
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | ✅ | - | 搜索查询词 |
| layers | array | ❌ | all | 限定搜索层级 |
| limit | integer | ❌ | 10 | 最大返回数 |
| time_range | string | ❌ | all | 时间范围筛选 |

## 返回结果格式
```json
{
  "results": [
    {
      "entry_id": "entry-uuid",
      "content": "...",
      "layer": "episodic",
      "relevance_score": 0.95,
      "tags": ["novel:chapter:15", "writer"],
      "timestamp": "2026-05-02T..."
    }
  ],
  "total": 8,
  "query_used": "{original_query}"
}
```

## 最佳实践
- ✅ 使用具体关键词而非泛化查询
- ✅ 组合多个关键词提高精度
- ✅ 指定layers缩小搜索范围提升性能
- ⚠️ 检查relevance_score < 0.5的结果可能不相关
- ⚠️ 大量结果时增加limit分批获取

## 绑定Agent
@memory-architect (主要) | 全部Agent均可调用

## 协作伙伴
@writer (创作参考) | @reviewer (审校对比) | @planner (设定查询)

## 强制规则关联
- **MT-002**: 与输入适配流水线同步触发
- **MM系列**: 检索后应验证数据完整性
