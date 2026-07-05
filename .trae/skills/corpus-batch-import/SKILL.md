# 语料批量导入 (corpus/batch-import)

## 目的
批量导入TXT小说文件并进行智能分块、编码检测和结构化处理。

## 触发场景
- 用户提到"导入小说"、"TXT转语料"、"批量处理TXT"
- @corpus-miner Agent被调度执行采集任务时
- 新增语料库资源时

## 执行步骤

### Step 1: 资源定位
1. 识别输入源（本地文件/百度网盘同步目录/用户指定路径）
2. 扫描目标目录获取所有.txt文件列表
3. 自动检测文件编码（UTF-8/GBK/GB2312/BIG5等）

### Step 2: 智能分块
1. 识别章节分割标记（"第X章"/"Chapter X"/"第X回"等）
2. 按章节边界切分文本
3. 对无明确分章的长文本按字数智能切分（建议5K-10K/块）

### Step 3: 元数据提取
1. 提取书名、作者（从文件名或正文开头）
2. 统计总字数、章节数
3. 评估文本质量（完整度/乱码率）

### Step 4: 结构化入库
1. 为每个章节生成唯一ID
2. 调用 `memory_remember` 存储到 episodic 层
3. 构建语料索引（书名→章节→内容的映射）
4. 更新语料库统计信息

### Step 5: 质量评分
1. 执行5维度质量评分:
   - completeness (完整性)
   - accuracy (准确性)
   - uniqueness (独特性)
   - usability (可用性)
   - diversity (多样性)
2. 生成质量报告
3. 标记低质量章节需人工审核

## 参数说明
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| source_path | string | ✅ | - | 源文件/目录路径 |
| encoding | string | ❌ | auto-detect | 文件编码 |
| chunk_size | integer | ❌ | 8000 | 分块大小(字符) |
| quality_threshold | float | ❌ | 0.7 | 质量评分阈值 |

## 输出格式
```json
{
  "import_id": "batch-{timestamp}",
  "source": "{source_path}",
  "stats": {
    "total_files": N,
    "total_chapters": M,
    "total_words": X,
    "encoding_detected": "UTF-8"
  },
  "quality_report": {
    "avg_score": 0.85,
    "chapters_needing_review": [...]
  },
  "storage_locations": {
    "episodic_entries": M,
    "index_updated": true
  }
}
```

## 绑定Agent
@corpus-miner (语料矿工)

## 协作伙伴
@analyzer (统计分析) | @memory-architect (入库) | @planner (策略规划)

## 注意事项
- ⚠️ 大文件(>50MB)需分批处理避免内存溢出
- ⚠️ 编码检测失败时尝试多种编码并人工确认
- ✅ 支持百度网盘本地同步目录作为输入源
