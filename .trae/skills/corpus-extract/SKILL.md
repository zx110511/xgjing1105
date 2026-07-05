# 语料提取与结构化 (corpus/extract)

## 目的
从原始文本中提取结构化信息，支持元数据提取、内容分块和语义标注。

## 触发场景
- 用户要求"提取信息"、"分析文本"、"结构化处理"
- @analyzer Agent执行数据分析任务时
- @corpus-miner完成导入后进行后处理时

## 执行步骤

### Step 1: 文本预处理
1. 编码标准化 (UTF-8)
2. 去除特殊字符和乱码
3. 统一换行符
4. 段落边界识别

### Step 2: 元数据提取
1. **基础元数据**
   - 书名/标题识别
   - 作者信息提取
   - 创建/修改时间戳
   - 文件大小统计

2. **内容元数据**
   - 章节标题识别 ("第X章"/"Chapter X"等模式)
   - 人物名称提取 (基于常见命名规则)
   - 地点/场景标记
   - 对话段落识别

### Step 3: 智能分块
1. 按章节边界切分（优先）
2. 无明确分章时按语义段落切分
3. 控制块大小在合理范围 (建议2K-8K字符)
4. 保持上下文连贯性

### Step 4: 结构化输出
```json
{
  "extract_id": "ext-{timestamp}",
  "source_file": "{filename}",
  "metadata": {
    "title": "...",
    "author": "...",
    "chapter_count": N,
    "total_chars": M,
    "language": "zh-CN"
  },
  "chunks": [
    {
      "chunk_id": "chunk-001",
      "type": "chapter|prologue|epilogue",
      "title": "第一章 XXX",
      "content_preview": "...",
      "char_count": 5000,
      "entities_detected": ["人物A", "地点B"]
    }
  ],
  "quality_metrics": {
    "completeness": 0.95,
    "encoding_valid": true,
    "structure_detected": true
  }
}
```

## 参数说明
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| input_text | string | ✅ | - | 待提取的原始文本 |
| extract_type | enum | ❌ | full | full/metadata/chunks/entities |
| chunk_size | integer | ❌ | 5000 | 分块大小(字符) |
| language | string | ❌ | auto-detect | 文本语言 |

## 输出格式
- JSON结构化数据 (默认)
- Markdown摘要报告 (可选)

## 绑定Agent
@analyzer (主要) | @corpus-miner (辅助)

## 协作伙伴
@memory-architect (存储结果) | @planner (设定参考)

## 注意事项
- ⚠️ 大文本(>100KB)需流式处理避免内存溢出
- ⚠️ 编码检测失败时尝试GBK/GB2312/BIG5回退
- ✅ 支持批量处理多个文件
