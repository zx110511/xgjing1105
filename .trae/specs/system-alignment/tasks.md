# 天机v9.1系统对齐项目 - 实现计划

## [x] Task 1: 创建统一工具-能力映射数据源 (ToolCategoryMapper)
- **Priority**: high
- **Depends On**: None
- **Description**: 
  - 在core/shared/下新建tool_category_mapper.py模块
  - 实现ToolCategoryMapper类，从CapabilityRegistry动态派生工具分类
  - 替代mcp_bridge.py中的硬编码`_TOOL_CATEGORIES`
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `programmatic` TR-1.1: ToolCategoryMapper能从能力矩阵正确派生所有工具分类
  - `programmatic` TR-1.2: mcp_bridge.py不再使用硬编码的`_TOOL_CATEGORIES`
  - `programmatic` TR-1.3: 工具分类与能力矩阵保持同步，修改能力矩阵后分类自动更新
- **Notes**: 需要处理工具分类名称与能力名称的映射关系

## [x] Task 2: 实现技能注册与Agent注册对账机制
- **Priority**: high
- **Depends On**: Task 1
- **Description**: 
  - 在core/shared/下新建registry_reconciler.py模块
  - 实现RegistryReconciler类，定期对比SkillRegistry和CapabilityRegistry
  - 每30分钟执行一次对账，发现不匹配时记录并告警
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `programmatic` TR-2.1: 对账机制能正确识别技能与Agent能力的不匹配
  - `programmatic` TR-2.2: 对账结果正确写入L3 Episodic
  - `programmatic` TR-2.3: 对账执行时间<500ms
- **Notes**: 需要定义对账规则和告警级别

## [x] Task 3: 验证并修复桌面快捷方式统一性
- **Priority**: high
- **Depends On**: None
- **Description**: 
  - 检查桌面快捷方式"C:\Users\Administrator\Desktop\天机v9.1.lnk"的目标路径
  - 确保快捷方式指向正确的启动入口(start_tianji.bat)
  - 如果快捷方式不存在或目标错误，自动创建或修复
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `programmatic` TR-3.1: 快捷方式目标路径与启动器脚本一致
  - `programmatic` TR-3.2: 快捷方式工作目录正确设置为天机v9.1根目录
  - `human-judgment` TR-3.3: 快捷方式图标正确显示
- **Notes**: 需要使用win32com或第三方库处理.lnk文件

## [x] Task 4: 强化后台进程排他性检查
- **Priority**: high
- **Depends On**: None
- **Description**: 
  - 在launcher/tianji_v91_launcher.py中强化排他性检查
  - 实现三重验证：端口占用检测+PID文件验证+健康检查API
  - 确保任何启动方式都遵循排他性原则
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `programmatic` TR-4.1: 端口被占用时新启动尝试自动终止
  - `programmatic` TR-4.2: PID文件存在且进程存活时新启动尝试自动终止
  - `programmatic` TR-4.3: 健康检查API返回正常时新启动尝试自动终止
  - `programmatic` TR-4.4: 排他性检查完成时间<3秒
- **Notes**: 需要处理PID文件过期但进程已死的边缘情况

## [x] Task 5: 确保托盘与服务状态同步
- **Priority**: medium
- **Depends On**: Task 4
- **Description**: 
  - 修改launcher/tianji_tray.py，实现托盘图标状态与后台服务状态同步
  - 添加定期健康检查线程，实时更新托盘图标状态
  - 确保右键菜单选项与服务状态匹配
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `human-judgment` TR-5.1: 托盘图标状态反映服务健康度（绿色=正常，红色=异常）
  - `programmatic` TR-5.2: 右键菜单中停止选项在服务未运行时禁用
  - `programmatic` TR-5.3: 服务状态变化后5秒内托盘图标更新
- **Notes**: 需要处理托盘图标更新的线程安全问题

## [x] Task 6: 编写集成测试并验证所有功能
- **Priority**: high
- **Depends On**: Tasks 1-5
- **Description**: 
  - 编写集成测试，验证所有功能点
  - 运行测试套件，确保所有测试通过
  - 生成测试报告
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3, AC-4, AC-5
- **Test Requirements**:
  - `programmatic` TR-6.1: 所有单元测试通过
  - `programmatic` TR-6.2: 所有集成测试通过
  - `human-judgment` TR-6.3: 测试报告内容完整、清晰
- **Notes**: 测试报告需要包含测试覆盖率、执行时间等关键指标
