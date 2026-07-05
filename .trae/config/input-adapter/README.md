# Input Adapter Configuration
# 元初系统 v5.3 - 从 reference/input-adapter/ 迁移

此目录包含Input Adapter 4层流水线的运行时配置:
- config.json: 全局配置 (4层启用状态+参数)
- extraction-rules.json: 参数提取规则库 (章节号/字数/风格识别)
- disambiguation-templates.json: 歧义消解话术模板 (25个场景)

配置加载路径:
  from core.input_adapter import load_config
  config = load_config()
