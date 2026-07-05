"""
天机v9.1 Agent系统 — 20智能体 + 流水线引擎
===========================================
五层Agent架构 (L0-L4) + AMIM集成桥接，为灵境分布式架构准备。

Agent层级:
    L0 基础设施守护:   铁卫(TieweiAgent)
    L1 数据/上下文层:   忆库(YikuAgent) / 洞察(DongchaAgent) / 律令(LulingAgent) / 灵犀(LingxiAgent)
    L2 决策/创作层:     天枢(TianshuAgent) / 文宗(WenzongAgent) / 经纬(JingweiAgent) /
                        妙笔(MiaobiAgent) / 明镜(MingjingAgent) / 天算(TiansuanAgent) / 矿师(KuangshiAgent)
    L3 执行/工具层:     百巧(BaiqiaoAgent) / 史官(ShiguanAgent) / 锦书(JinshuAgent)
    L4 运维/观测层:     千里(QianliAgent) / 工造(GongzaoAgent) / 镇山(ZhenshanAgent) / 追光(ZhuiguangAgent)

流水线引擎:
    Pipeline (main entry)
    ├── PipelineLogger  - Centralized metrics & tracing
    ├── OrchestratorAgent - Priority scheduler + state machine
    ├── BuildAgent     - Code→Package automation
    ├── TestAgent      - SG-0~4 verification
    └── RecoveryAgent  - Auto-diagnosis & fix
"""

from agents.pipeline_logger import PipelineLogger, LogLevel, LogEntry
from agents.orchestrator import OrchestratorAgent, PipelineState, Task, TaskPriority

from agents.tiewei import TieweiAgent
from agents.yiku import YikuAgent
from agents.dongcha import DongchaAgent
from agents.luling import LulingAgent
from agents.lingxi import LingxiAgent
from agents.tianshu import TianshuAgent
from agents.wenzong import WenzongAgent
from agents.jingwei import JingweiAgent
from agents.miaobi import MiaobiAgent
from agents.mingjing import MingjingAgent
from agents.tiansuan import TiansuanAgent
from agents.kuangshi import KuangshiAgent
from agents.baiqiao import BaiqiaoAgent
from agents.shiguan import ShiguanAgent
from agents.jinshu import JinshuAgent
from agents.qianli import QianliAgent
from agents.gongzao import GongzaoAgent
from agents.zhenshan import ZhenshanAgent
from agents.zhuiguang import ZhuiguangAgent

__version__ = "2.0.0"
__all__ = [
    "PipelineLogger", "LogLevel", "LogEntry",
    "OrchestratorAgent", "PipelineState", "Task", "TaskPriority",
    "TieweiAgent", "YikuAgent", "DongchaAgent", "LulingAgent", "LingxiAgent",
    "TianshuAgent", "WenzongAgent", "JingweiAgent", "MiaobiAgent", "MingjingAgent",
    "TiansuanAgent", "KuangshiAgent", "BaiqiaoAgent", "ShiguanAgent", "JinshuAgent",
    "QianliAgent", "GongzaoAgent", "ZhenshanAgent", "ZhuiguangAgent",
]
