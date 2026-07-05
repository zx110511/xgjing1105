# 成品格式化导出 (novel/format-export)

## 目的
将创作文本转化为出版级成品，支持多格式导出。

## 触发场景
- 用户要求"排版"、"导出"、"生成EPUB/DOCX"
- @novel-formatter Agent被调度时
- 工业化生产流水线的最后阶段(第⑩步)

## 支持的输出格式

### 1. TXT (纯文本)
- 换行规范统一
- 段落缩进2个全角字符
- 对话独立段落，双引号包裹

### 2. Markdown
- 标题层级语法 (# ## ###)
- 列表、引用、代码块
- 保持原始结构清晰

### 3. EPUB (电子书)
- 章节自动分割
- 目录(TOC)生成
- 元数据嵌入(书名/作者/ISBN占位)
- CSS样式美化

### 4. DOCX (Word文档)
- 样式应用(标题/正文/对话)
- 页眉页脚设置
- 自动页码
- 打印优化排版

## 执行流程

### Phase 1: 标准化预处理
1. **标题规范化**
   - 居中对齐
   - 「第X章」格式统一
2. **段落格式化**
   - 首行缩进2个全角字符
   - 段间距统一
3. **对话格式统一**
   - 独立段落
   - 双引号包裹
   - 说话人标签可选

### Phase 2: 注释与强调处理
1. 注释格式: `[注X]` 上标
2. 专有名词: 《》包裹
3. 场景切换: 空行 + 分隔符(※或---)

### Phase 3: 质量检查
1. ✅ 页码连续性验证
2. ✅ 断行规范检查
3. ✅ 标点符号一致性
4. ✅ 编码正确性确认(UTF-8 BOM)

### Phase 4: 导出生成
1. 选择目标格式
2. 应用对应模板
3. 生成索引文件:
   - 人物索引
   - 地名索引
   - 设定术语索引
4. 输出到指定路径

## 参数说明
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| input_source | string/path | ✅ | - | 输入文件或目录 |
| output_format | enum | ❌ | TXT | TXT/MD/EPUB/DOCX |
| output_path | string | ❌ | ./output/ | 输出目录 |
| generate_toc | boolean | ❌ | true | 是否生成目录 |
| generate_index | boolean | ❌ | true | 是否生成索引 |

## 输出结构示例
```
output/
├── novel_title.epub        # 电子书
├── novel_title.docx         # Word文档
├── novel_title.txt          # 纯文本
├── TOC.md                   # 目录
├── index_characters.md      # 人物索引
├── index_locations.md       # 地名索引
└── quality_report.md        # 质量报告
```

## 绑定Agent
@novel-formatter (成品匠)

## 协作伙伴
@writer (原始文本) | @reviewer (格式审校) | @version-keeper (版本对齐) | @editor (交付确认)

## 出版级质量标准
- 标点错误率 < 0.1%
- 格式一致性 > 99%
- 编码正确性 100%
- 可直接提交出版社/平台
