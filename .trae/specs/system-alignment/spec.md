# 天机v9.1系统对齐项目 - 产品需求文档

## Overview
- **Summary**: 实现MCP技能系统与智能调度系统的数据对齐，以及后台进程+托盘运行+桌面快捷方式的完全统一与排他性保障
- **Purpose**: 解决MCP工具分类与Agent能力矩阵的重复定义问题，建立技能注册与Agent注册的定期对账机制，确保系统启动的唯一性和稳定性
- **Target Users**: 天机系统管理员、开发人员、最终用户

## Goals
- 统一MCP工具分类与Agent能力矩阵的数据源，消除重复定义
- 建立SkillRegistry与CapabilityRegistry的定期对账机制
- 确保"后台进程+托盘运行+桌面快捷方式"的完全统一与排他性
- 实现全自动化执行规划、科学审计与修复

## Non-Goals (Out of Scope)
- 不修改Agent调度核心算法逻辑
- 不改变MCP工具的具体实现
- 不引入新的Agent或工具
- 不修改现有API接口

## Background & Context
- 当前`_TOOL_CATEGORIES`（mcp_bridge.py）与能力矩阵的`capabilities`字段存在重复定义
- `SkillRegistry`与`CapabilityRegistry`独立运行，缺乏同步机制
- 桌面快捷方式、后台服务、托盘运行可能存在不一致状态
- 系统需要确保唯一实例运行，避免端口冲突和数据竞争

## Functional Requirements
- **FR-1**: 创建统一的工具-能力映射数据源，替代`_TOOL_CATEGORIES`硬编码
- **FR-2**: 实现SkillRegistry与CapabilityRegistry的定期对账机制
- **FR-3**: 确保桌面快捷方式指向正确的启动入口
- **FR-4**: 实现后台进程的排他性检查（端口+PID+健康检查三重验证）
- **FR-5**: 确保托盘图标与后台服务状态同步

## Non-Functional Requirements
- **NFR-1**: 对账机制执行时间<500ms，不影响系统响应
- **NFR-2**: 排他性检查必须在3秒内完成
- **NFR-3**: 所有状态变更必须记录到L3 Episodic
- **NFR-4**: 系统启动失败时必须提供清晰的错误信息和修复建议

## Constraints
- **Technical**: Python 3.12 / Windows环境 / UTF-8-SIG编码
- **Business**: 不中断现有运行的v9.1系统
- **Dependencies**: 依赖ICME记忆系统进行状态记录

## Assumptions
- 天机v9.1当前运行在端口8771
- 桌面快捷方式已存在于C:\Users\Administrator\Desktop\天机v9.1.lnk
- 启动器脚本已存在于launcher/tianji_v91_launcher.py

## Acceptance Criteria

### AC-1: 统一工具-能力映射数据源
- **Given**: `_TOOL_CATEGORIES`硬编码存在于mcp_bridge.py
- **When**: 系统启动时加载能力矩阵
- **Then**: MCP工具分类自动从能力矩阵派生，不再依赖硬编码的`_TOOL_CATEGORIES`
- **Verification**: `programmatic`
- **Notes**: 新增`ToolCategoryMapper`类实现动态映射

### AC-2: 技能注册与Agent注册对账机制
- **Given**: SkillRegistry和CapabilityRegistry独立运行
- **When**: 系统运行时每30分钟执行一次对账
- **Then**: 发现技能与Agent能力不匹配时自动记录并告警
- **Verification**: `programmatic`
- **Notes**: 对账结果写入L3 Episodic和日志

### AC-3: 桌面快捷方式统一性
- **Given**: 桌面快捷方式存在
- **When**: 系统启动或快捷方式点击时
- **Then**: 快捷方式指向唯一的启动入口（start_tianji.bat或tianji_v91_launcher.py）
- **Verification**: `programmatic`
- **Notes**: 快捷方式目标路径必须与启动器脚本一致

### AC-4: 后台进程排他性
- **Given**: 系统启动时
- **When**: 检测到已有进程占用端口8771或PID文件存在
- **Then**: 新启动尝试自动终止，并提示用户已有实例运行
- **Verification**: `programmatic`
- **Notes**: 三重验证：端口占用+PID文件+健康检查API

### AC-5: 托盘与服务状态同步
- **Given**: 托盘图标运行中
- **When**: 后台服务状态变化（启动/停止/异常）
- **Then**: 托盘图标状态实时更新，并提供相应的右键菜单选项
- **Verification**: `human-judgment`
- **Notes**: 托盘图标颜色/状态反映服务健康度

## Open Questions
- [ ] 桌面快捷方式的具体格式和内容需要确认
- [ ] 是否需要支持手动刷新快捷方式的功能
- [ ] 对账机制的具体告警方式需要确定
