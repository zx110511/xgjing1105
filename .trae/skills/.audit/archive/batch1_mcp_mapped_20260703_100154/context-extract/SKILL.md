# 上下文提取 (context/extract)

## 目的
从输入文本中自动提取关键上下文信息，包括关键词、实体、意图和情感倾向

## 触发场景
- 用户消息到达时的自动预处理
- 需要理解用户真实意图
- 从长文本中快速提取结构化信息
- 为后续任务路由提供依据

## 执行步骤
### Step 1: 文本预处理
1. 清理文本(去除特殊字符/规范化空白)
2. 分句分段
3. 识别语言类型(中文为主)

### Step 2: 多维提取
根据extract_types参数执行对应提取:

#### 2.1 关键词提取 (keywords)
- 核心名词提取(人名/地名/专有名词)
- 动作词识别(操作指令)
- 形容词/副词筛选(修饰限定)
- 权重排序(TF-IDF/TextRank)

#### 2.2 实体识别 (entities)
- 人物实体: 主角/配角/NPC名称
- 地点实体: 场景/区域/建筑
- 组织实体: 势力/门派/机构
- 时间实体: 绝对时间/相对时间/时间段
- 数量实体: 数字/等级/比例

#### 2.3 意图识别 (intent)
- 创作意图: 写/改/扩/缩/续
- 操作意图: 查/删/改/导/导出
- 咨询意图: 什么是/怎么做/为什么
- 反馈意图: 好/坏/修改建议

#### 2.4 情感分析 (sentiment)
- 极性判断: 正面/负面/中性
- 强度量化: 0-1情感强度
- 情感分类: 喜欢/厌恶/期待/焦虑/愤怒/平静

### Step 3: 结果整合
1. 合并各维度提取结果
2. 交叉验证一致性
3. 生成结构化输出
4. 提供处理建议(suggestions)

## 参数说明
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| input_text | string | ✅ | - | 待分析的原始文本 |
| extract_types | array | ❌ | ["keywords"] | 提取类型: keywords/entities/intent/sentiment |

## 输出格式
```json
{
  "extract_id": "ctx-{timestamp}",
  "input_length": N,
  "keywords": [
    {"word": "林远", "weight": 0.95, "type": "person"},
    {"word": "突破", "weight": 0.82, "type": "action"}
  ],
  "entities": {
    "persons": ["林远", "苏清"],
    "locations": ["天元城", "秘境"],
    "organizations": ["天道宗"],
    "times": ["三日后", "子时"]
  },
  "intent": {
    "primary": "writing",
    "confidence": 0.88,
    "details": "创作新章节",
    "sub_intents": ["novel_chapter_create"]
  },
  "sentiment": {
    "polarity": "positive",
    "intensity": 0.72,
    "emotions": [{"type": "expectation", "score": 0.65}]
  },
  "suggestions": [
    "用户意图为章节创作，建议路由到@writer",
    "检测到角色名'林远'，可加载其角色卡"
  ]
}
```

## MCP工具绑定
**context_extract** - agent-framework MCP Server

## 绑定Agent
@context-extractor

## 协作伙伴
@orchestrator | @memory-architect | @rule-evaluator

## 质量标准
- 关键词提取准确率 >= 85%
- 实体识别召回率 >= 80%
- 意图识别准确率 >= 90%
- 处理延迟 < 200ms
