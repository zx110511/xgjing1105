# 元初系统 Git LFS 大文件管理规范 v1.0

## 1. 策略总览

### 1.1 三类文件处理策略

| 文件类别 | 处理策略 | 配置位置 | 示例 |
|---------|---------|---------|------|
| **LFS管理** | Git LFS跟踪，版本控制 | `.gitattributes` | 模型文件、重要数据集、发布归档 |
| **完全忽略** | 不纳入版本控制 | `.gitignore` | 运行时数据库、缓存、日志、构建产物 |
| **正常跟踪** | 标准Git管理 | 无需配置 | 源代码、配置文件、文档 |

### 1.2 决策流程

```
新增文件 > 10MB？
  ├── 是 → 是否需要版本控制？
  │        ├── 是 → .gitattributes 添加 LFS 规则
  │        └── 否 → .gitignore 添加忽略规则
  └── 否 → 正常Git跟踪
```

## 2. 当前 LFS 管理范围

### 2.1 模型文件
```
*.pkl, *.pth, *.pt     — Python/PyTorch 模型权重
*.h5, *.pb, *.onnx     — TensorFlow/Keras/ONNX 模型
*.bin                  — 通用二进制模型
```

### 2.2 数据文件
```
*.csv, *.xlsx, *.xls   — 结构化数据表格
*.parquet              — 列式存储数据
```

### 2.3 归档文件
```
*.tar.gz, *.zip, *.7z  — 压缩归档
```

### 2.4 媒体与文档
```
*.pdf                  — 文档
*.mp4, *.mp3, *.wav    — 音视频媒体
```

## 3. 配置文件职责

### 3.1 `.gitignore` — 排除不需要版本控制的文件
- 运行时数据：数据库、缓存、日志
- 构建产物：dist、build、target
- 开发环境：IDE配置、虚拟环境
- 敏感信息：环境变量、密钥
- 临时文件：bak、tmp、old

### 3.2 `.gitattributes` — 定义文件Git行为
- LFS管理：大文件使用Git LFS存储
- 换行符处理：跨平台文本文件
- 语言属性：linguist统计

## 4. 操作指南

### 4.1 添加新的 LFS 文件

```bash
# 确保文件类型已在 .gitattributes 中配置
# 然后用正常方式添加
git add path/to/large_file.csv
git commit -m "添加数据集"
git push
```

### 4.2 验证 LFS 配置

```bash
# 查看 LFS 跟踪的文件类型
git lfs track

# 查看 LFS 管理的文件列表
git lfs ls-files

# 查看 LFS 存储使用情况
git lfs status
```

### 4.3 迁移已有文件到 LFS

```bash
# 将历史中的大文件迁移到 LFS
git lfs migrate import --include="*.csv,*.xlsx,*.zip" --everything

# 仅迁移当前分支
git lfs migrate import --include="*.pkl,*.pt" --include-ref=refs/heads/main
```

## 5. 最佳实践

### 5.1 文件大小阈值
- **≥ 10MB**：建议使用 LFS
- **≥ 100MB**：必须使用 LFS（GitHub限制）
- **< 1MB**：正常Git跟踪即可

### 5.2 应该使用 LFS 的场景
- 机器学习模型权重文件
- 重要的参考数据集
- 官方发布归档包
- UI设计资源（大尺寸）

### 5.3 不应该使用 LFS 的场景
- 日志文件和调试输出
- 依赖包目录（node_modules、.venv等）
- 构建中间产物
- 临时/缓存文件

### 5.4 常见错误

| 错误 | 正确做法 |
|------|---------|
| 在 `.gitignore` 中忽略 LFS 管理的文件类型 | `.gitignore` 不包含 LFS 管理的扩展名 |
| 用 LFS 管理所有大文件 | 仅对需要版本控制的文件启用 LFS |
| 忽略 `.gitattributes` 不提交 | `.gitattributes` 必须提交到仓库 |

## 6. 团队协作

### 6.1 新成员入职
```bash
# 安装 Git LFS
git lfs install

# 克隆仓库（自动下载 LFS 文件）
git clone <repo-url>

# 手动拉取 LFS 文件（如有遗漏）
git lfs pull
```

### 6.2 常见问题

**Q: 拉取时 LFS 文件下载失败？**
```bash
git lfs fetch --all
git lfs checkout
```

**Q: 如何判断文件是否被 LFS 管理？**
```bash
git lfs ls-files | grep <filename>
```

**Q: 误将大文件提交到普通 Git？**
```bash
git lfs migrate import --include="<file-pattern>" --everything
```