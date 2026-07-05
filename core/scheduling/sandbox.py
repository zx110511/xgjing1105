r"""
天机调度 - 隔离执行上下文工厂 (Execution Sandbox) [v10-ready]
==============================================================
借鉴 Hermes 的隔离上下文设计: 子代理只拥有 goal + context 字段中的信息，
不知道父代理的任何对话历史，实现纯净的沙箱式执行上下文。

从 core/intelligent_scheduler.py 拆分而来 (原 IsolatedContextFactory)。
"""

from typing import List

from core.scheduling import SubAgentTask


class ExecutionSandbox:
    """隔离执行上下文工厂: 子代理只拥有 goal + context 字段中的信息"""

    @staticmethod
    def build_system_prompt(task: SubAgentTask) -> str:
        return f"""你是天机记忆系统的子代理调度器。你被委派执行一个孤立任务。

委派目标: {task.goal}

任务上下文:
{task.context}

可用工具集: {', '.join(task.toolsets)}

执行规则:
1. 你拥有全新上下文，不知道父代理的任何对话历史
2. 完成任务后，返回结构化摘要:
   - summary: 你做了什么 (2-3句话)
   - findings: 你的发现 (列表)
   - files_modified: 修改的文件 (列表)
   - errors: 遇到的错误 (列表)
3. 如果遇到无法解决的错误，标记为失败并说明原因
4. 严格遵守超时限制: {task.timeout_s}秒"""

    @staticmethod
    def build_delegation_prompt(parent_goal: str, sub_tasks: List[SubAgentTask]) -> str:
        tasks_desc = "\n".join(
            f"{i+1}. {t.goal} (工具集: {', '.join(t.toolsets)})"
            for i, t in enumerate(sub_tasks)
        )
        return f"""我需要委派以下{len(sub_tasks)}个子任务来并行执行。

主目标: {parent_goal}

子任务:
{tasks_desc}

请为每个子任务提供充足的上下文（如同Hermes的delegate_task），
确保每个子代理拥有完成任务所需的全部信息。"""


# 兼容别名: 原 Hermes 命名
IsolatedContextFactory = ExecutionSandbox
