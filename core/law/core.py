"""法则核心枚举和数据类 — 从law_domain.py提取"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

try:
    from core.shared.config import MEMORY_DATA_PATH
except ImportError:
    from ...config import MEMORY_DATA_PATH

_DATA_DIR = MEMORY_DATA_PATH
_LAW_DIR = _DATA_DIR / ".law_domain"
_LAW_INDEX = _LAW_DIR / "law_index.json"
_LAW_STATS = _LAW_DIR / "law_stats.json"


class LawDomain(str, Enum):
    PROCESS = "process"
    PATH = "path"
    MEMORY = "memory"
    SECURITY = "security"
    CODE_QUALITY = "code_quality"
    DEPLOY = "deploy"
    AGENT = "agent"

    @classmethod
    def prefix(cls, domain: LawDomain) -> str:
        _PREFIX_MAP = {
            cls.PROCESS: "PR",
            cls.PATH: "PATH",
            cls.MEMORY: "MEM",
            cls.SECURITY: "SEC",
            cls.CODE_QUALITY: "CODE",
            cls.DEPLOY: "DEPLOY",
            cls.AGENT: "AGENT",
        }
        return _PREFIX_MAP.get(domain, "XX")


class LawType(str, Enum):
    PREVENTION = "prevention"
    RECOVERY = "recovery"
    OPTIMIZATION = "optimization"
    GOVERNANCE = "governance"

    @classmethod
    def label_cn(cls, lt: LawType) -> str:
        return {
            cls.PREVENTION: "预防型",
            cls.RECOVERY: "恢复型",
            cls.OPTIMIZATION: "优化型",
            cls.GOVERNANCE: "治理型",
        }.get(lt, lt.value)


class LawPriority(str, Enum):
    P0_CRITICAL = "P0"
    P1_HIGH = "P1"
    P2_MEDIUM = "P2"
    P3_LOW = "P3"

    @classmethod
    def label_cn(cls, lp: LawPriority) -> str:
        return {
            cls.P0_CRITICAL: "P0-强制执行",
            cls.P1_HIGH: "P1-强烈推荐",
            cls.P2_MEDIUM: "P2-建议遵守",
            cls.P3_LOW: "P3-可选参考",
        }.get(lp, lp.value)


class LawStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"

    @classmethod
    def label_cn(cls, ls: LawStatus) -> str:
        return {
            cls.DRAFT: "草稿",
            cls.VALIDATED: "已验证",
            cls.ACTIVE: "生效中",
            cls.DEPRECATED: "已废弃",
            cls.SUPERSEDED: "已被替代",
        }.get(ls, ls.value)


@dataclass
class EmpiricalLaw:
    law_id: str
    domain: LawDomain
    law_type: LawType
    priority: LawPriority
    status: LawStatus
    title: str
    principle: str
    steps: list[str]
    trigger_scenarios: list[str]
    violation_consequences: list[str]
    enforcement_methods: list[str]
    source_memory_ids: list[str]
    source_experience_summary: str
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    validated_at: str = ""
    activated_at: str = ""
    activation_count: int = 0
    last_optimized_at: str = ""
    tags: list[str] = field(default_factory=list)
    related_law_ids: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["domain"] = self.domain.value
        d["law_type"] = self.law_type.value
        d["priority"] = self.priority.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> EmpiricalLaw:
        d["domain"] = LawDomain(d["domain"])
        d["law_type"] = LawType(d["law_type"])
        d["priority"] = LawPriority(d["priority"])
        d["status"] = LawStatus(d["status"])
        return cls(**d)


@dataclass
class ExperiencePattern:
    pattern_id: str
    source_layer: str
    source_id: str
    raw_content: str
    extracted_problem: str
    extracted_root_cause: str
    extracted_solution: str
    extracted_prevention: str
    domain_hint: LawDomain | None = None
    type_hint: LawType | None = None
    priority_hint: LawPriority | None = None
    frequency: int = 1
    similar_pattern_ids: list[str] = field(default_factory=list)
    already_has_law: bool = False
    law_id_if_any: str = ""
    is_fault_record: bool = False
    tags: list[str] = field(default_factory=list)
    value_score: int = 0
    llm_enhanced: bool = False
    meta: dict = field(default_factory=dict)


EXPERIENCE_MINING_PATTERNS = [
    {
        "name": "反复犯错模式",
        "regex": r"(反复|重复|再次|又|屡次|多次|连续).{0,20}(犯错|出错|失败|出现|发生|报错|崩溃)",
        "domain": LawDomain.PROCESS,
        "type": LawType.PREVENTION,
        "priority": LawPriority.P0_CRITICAL,
        "extraction_prompt": "此问题反复出现，说明缺乏预防机制。请提取：1)什么操作导致问题反复？2)如何从流程上根本预防？",
    },
    {
        "name": "路径硬编码模式",
        "regex": r"(硬编码|绝对路径|写死).{0,30}(path|路径|目录|文件夹|C:\\\\|D:\\\\)",
        "domain": LawDomain.PATH,
        "type": LawType.PREVENTION,
        "priority": LawPriority.P0_CRITICAL,
        "extraction_prompt": "发现路径硬编码问题。请提取：1)哪些路径被硬编码？2)应改为什么形式的配置？3)如何防止未来再犯？",
    },
    {
        "name": "进程残留模式",
        "regex": r"(旧进程|残留|僵尸|未退出|仍在运行|端口占用|PID.{0,10}(冲突|占用|存在))",
        "domain": LawDomain.PROCESS,
        "type": LawType.RECOVERY,
        "priority": LawPriority.P0_CRITICAL,
        "extraction_prompt": "发现进程管理问题。请提取：1)什么场景导致旧进程残留？2)正确的进程替换流程是什么？3)需要哪些验证步骤？",
    },
    {
        "name": "记忆遗漏模式",
        "regex": r"(忘记|遗漏|缺失|未录入|未记录|未同步|丢失).{0,20}(记忆|记录|日志|归档|存储)",
        "domain": LawDomain.MEMORY,
        "type": LawType.PREVENTION,
        "priority": LawPriority.P1_HIGH,
        "extraction_prompt": "发现记忆记录遗漏。请提取：1)什么情况下会忘记记录？2)应该何时触发记忆写入？3)如何自动化防止遗漏？",
    },
    {
        "name": "命名不一致模式",
        "regex": r"(命名|名称|标题).{0,15}(不一致|过时|错误|旧版|需要更新|不统一)",
        "domain": LawDomain.CODE_QUALITY,
        "type": LawType.GOVERNANCE,
        "priority": LawPriority.P1_HIGH,
        "extraction_prompt": "发现命名一致性问题。请提取：1)哪些命名需要统一？2)标准命名规范是什么？3)如何自动检测违规？",
    },
    {
        "name": "依赖缺失模式",
        "regex": r"(ModuleNotFoundError|ImportError|依赖|缺少|缺失|找不到).{0,20}(模块|包|library|package)",
        "domain": LawDomain.DEPLOY,
        "type": LawType.PREVENTION,
        "priority": LawPriority.P1_HIGH,
        "extraction_prompt": "发现依赖管理问题。请提取：1)什么导致依赖缺失？2)正确的依赖管理流程是什么？3)如何提前检测？",
    },
    {
        "name": "数据竞争模式",
        "regex": r"(竞态|race.?condition|并发|同时写|冲突|锁|mutex|thread)",
        "domain": LawDomain.PROCESS,
        "type": LawType.PREVENTION,
        "priority": LawPriority.P0_CRITICAL,
        "extraction_prompt": "发现并发安全问题。请提取：1)哪些资源存在竞态条件？2)正确的并发控制方案是什么？3)如何验证线程安全？",
    },
    {
        "name": "回滚能力缺失模式",
        "regex": r"(无法回滚|不能撤销|不可逆|没有备份|无法恢复|数据丢失|覆盖)",
        "domain": LawDomain.DEPLOY,
        "type": LawType.RECOVERY,
        "priority": LawPriority.P0_CRITICAL,
        "extraction_prompt": "发现回滚能力不足。请提取：1)什么操作是不可逆的？2)应该建立什么样的备份机制？3)回滚流程是什么？",
    },
]
