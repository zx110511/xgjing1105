# 安全审计 (Security Audit) — @zhenshan

## 触发条件

- 新依赖引入
- 代码变更涉及敏感操作
- 定期安全巡检

## 执行流程

1. **文件扫描**：scan_file（所有变更文件）
2. **依赖审计**：scan_dependencies（pip/npm）
3. **权限检查**：check_permissions（文件/目录权限）
4. **密钥检测**：secret_detect（硬编码密钥/Token）
5. **综合报告**：vulnerability_report

## MCP 工具

- `security-scanner`: scan_file, scan_dependencies, check_permissions, secret_detect, audit_log, vulnerability_report
- `command-executor`: execute_command

## 检测项目

```yaml
secrets: [API_KEY, TOKEN, PASSWORD, PRIVATE_KEY]
vulnerabilities: [CVE, OWASP Top-10, SQL注入, XSS]
permissions: [world-writable, suid, 敏感文件]
compliance: [PII泄露, 日志敏感信息]
```

## 联动 Agent

- @tiewei (测试) — 安全扫描嵌入测试门禁
- @luling (规则) — 违反规则则阻断
- @qianli (运维) — 高危漏洞告警
