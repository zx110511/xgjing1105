# core/memory/dual_process.py [v10-ready]
"""双过程固结器 — L3 Episodic → L4 Semantic 知识提炼

模拟人类记忆固结的双过程理论:
- 快过程(System 1): 基于规则的模式匹配，快速识别可合并的经历
- 慢过程(System 2): DeepSeek深度分析，提炼共性生成语义知识

流水线:
1. Harvest — 从L3批量读取近期episodic记忆
2. Cluster — DeepSeek对记忆进行主题聚类
3. Distill — 对每个聚类提炼共性，生成语义摘要
4. Gate — QualityGate判决（PASS/REJECT/DOWNGRADE）
5. Commit — 通过判决的语义条目写入L4
6. Report — 生成固结报告（统计+事件发布）

核心设计：DeepSeek驱动决策 + 自动化全流程 + 主动定时触发

[v10-ready]
"""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "IConsolidator",
    "ConsolidationReport",
    "ConsolidationConfig",
    "DualProcessConsolidator",
]


# ═══════════════════════════════════════════════════════════════════
# 协议定义 — 固结器对外契约
# ═══════════════════════════════════════════════════════════════════
@runtime_checkable
class IConsolidator(Protocol):
    """固结器协议  [v10-ready]

    定义固结器对外暴露的最小行为契约，便于上层以接口编程、依赖注入。
    """

    async def consolidate(
        self,
        since: datetime | None = None,
        batch_size: int = 50,
    ) -> "ConsolidationReport":
        """执行一次固结，返回报告。"""
        ...

    async def estimate_consolidation_candidates(self) -> int:
        """估算当前待固结的候选记忆数量。"""
        ...


# ═══════════════════════════════════════════════════════════════════
# 数据类 — 报告与配置
# ═══════════════════════════════════════════════════════════════════
@dataclass
class ConsolidationReport:
    """固结执行报告  [v10-ready]

    汇总单次固结循环的输入、处理、质量门禁、输出与自进化指标。
    """

    started_at: datetime
    completed_at: datetime

    # 输入
    candidates_found: int  # L3中找到的候选数
    batch_size: int

    # 处理
    clusters_formed: int  # 形成的主题聚类数
    distilled_count: int  # 成功提炼的语义条目数

    # 质量门禁
    passed_gate: int  # 通过QualityGate的数量
    rejected: int  # 被拒绝的数量
    downgraded: int  # 被降级的数量

    # 输出
    committed_to_l4: int  # 最终写入L4的数量

    # 自进化指标
    success_rate: float  # passed_gate / distilled_count
    duration_seconds: float

    # 错误
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，便于事件发布与日志记录。

        Returns:
            dict[str, Any]: 报告的可序列化快照。
        """
        return {
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "candidates_found": self.candidates_found,
            "batch_size": self.batch_size,
            "clusters_formed": self.clusters_formed,
            "distilled_count": self.distilled_count,
            "passed_gate": self.passed_gate,
            "rejected": self.rejected,
            "downgraded": self.downgraded,
            "committed_to_l4": self.committed_to_l4,
            "success_rate": round(self.success_rate, 4),
            "duration_seconds": round(self.duration_seconds, 4),
            "errors": list(self.errors),
        }


@dataclass
class ConsolidationConfig:
    """固结配置  [v10-ready]

    控制固结批量、聚类规模、置信度阈值、主动触发间隔与自进化参数。
    """

    default_batch_size: int = 50
    min_cluster_size: int = 3  # 至少3条相关记忆才形成聚类
    max_cluster_size: int = 20  # 单个聚类最多20条
    confidence_threshold: float = 0.7  # 提炼结果置信度阈值
    auto_trigger_interval_seconds: int = 3600  # 主动触发间隔（1小时）
    enable_system2: bool = True  # 是否启用DeepSeek深度分析

    # 自进化参数
    adaptive_batch_size: bool = True  # 根据历史成功率自适应调整batch_size
    success_rate_history: list[float] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# 双过程固结器实现
# ═══════════════════════════════════════════════════════════════════
class DualProcessConsolidator:
    """双过程固结器实现  [v10-ready]

    从 L3(episodic) 批量提取经历记忆，经 DeepSeek 聚类与提炼，
    通过 QualityGate 判决后写入 L4(semantic)。所有外部依赖均为可选，
    任一缺失时对应环节降级但不崩溃。

    Args:
        episodic_core: L3 MemoryCore 实例（读取源）。
        semantic_core: L4 MemoryCore 实例（写入目标）。
        llm_driver: DeepSeek 驾驶者（聚类+提炼的核心大脑）。
        gate: QualityGate 实例（可选，质量判决）。
        event_bus: IEventBus 实例（可选，事件发布）。
        config: ConsolidationConfig（可选，配置参数）。
    """

    def __init__(
        self,
        episodic_core: Any = None,  # L3 MemoryCore
        semantic_core: Any = None,  # L4 MemoryCore
        llm_driver: Any = None,  # DeepSeek（核心）
        gate: Any = None,  # QualityGate（可选）
        event_bus: Any = None,  # EventBus（可选）
        config: ConsolidationConfig | None = None,
    ) -> None:
        """初始化固结器并保存可选依赖。"""
        self._episodic = episodic_core
        self._semantic = semantic_core
        self._llm = llm_driver
        self._gate = gate
        self._event_bus = event_bus
        self._config = config or ConsolidationConfig()
        self._run_errors: list[str] = []

    # ------------------------------------------------------------------
    # 对外 API
    # ------------------------------------------------------------------
    async def consolidate(
        self,
        since: datetime | None = None,
        batch_size: int = 50,
    ) -> ConsolidationReport:
        """执行一次固结循环（全自动流水线）。

        Args:
            since: 仅固结该时间点之后的经历；None 表示不限。
            batch_size: 单次读取的候选上限（受自进化策略调节）。

        Returns:
            ConsolidationReport: 本次固结的统计报告。
        """
        started = datetime.now()
        self._run_errors = []
        effective_batch = self._resolve_batch_size(batch_size)
        report = self._new_report(started, effective_batch)

        memories = await self._harvest(since, effective_batch)
        report.candidates_found = len(memories)

        clusters = await self._cluster(memories)
        report.clusters_formed = len(clusters)

        await self._process_clusters(clusters, report)

        self._finalize_report(report, started)
        self._record_evolution(report)
        self._publish_event("consolidation.completed", report.to_dict())
        return report

    async def estimate_consolidation_candidates(self) -> int:
        """估算待固结候选数。

        Returns:
            int: L3 当前条目数；episodic_core 缺失时返回 0。
        """
        if self._episodic is None:
            return 0
        counter = getattr(self._episodic, "count", None)
        if counter is None:
            return 0
        try:
            value = await self._maybe_await(counter())
            return int(value)
        except Exception as exc:  # pragma: no cover - 防御性降级
            self._run_errors.append(f"estimate失败: {exc}")
            return 0

    # ------------------------------------------------------------------
    # 流水线：Harvest
    # ------------------------------------------------------------------
    async def _harvest(
        self, since: datetime | None, batch_size: int
    ) -> list[dict]:
        """从 L3 读取候选记忆。

        Args:
            since: 时间下界（含），None 表示不过滤。
            batch_size: 读取上限。

        Returns:
            list[dict]: 候选经历记忆；episodic_core 缺失时为空。
        """
        if self._episodic is None:
            return []
        searcher = getattr(self._episodic, "search", None)
        if searcher is None:
            return []
        try:
            results = await self._maybe_await(searcher("", limit=batch_size))
        except Exception as exc:
            self._run_errors.append(f"harvest失败: {exc}")
            return []
        memories = [m for m in (results or []) if isinstance(m, dict)]
        if since is not None:
            memories = [m for m in memories if self._memory_after(m, since)]
        return memories[:batch_size]

    def _memory_after(self, memory: dict, since: datetime) -> bool:
        """判断记忆是否发生在 since 之后。

        Args:
            memory: 记忆字典（含 timestamp/event_time 等字段）。
            since: 时间下界。

        Returns:
            bool: 无法解析时间戳时保守返回 True（纳入候选）。
        """
        ts = self._extract_timestamp(memory)
        if ts is None:
            return True
        return ts >= since.timestamp()

    @staticmethod
    def _extract_timestamp(memory: dict) -> float | None:
        """从记忆字典提取 epoch 时间戳。

        Args:
            memory: 记忆字典。

        Returns:
            float | None: 解析得到的 epoch 秒；无法解析时为 None。
        """
        raw = memory.get("timestamp")
        if isinstance(raw, (int, float)):
            return float(raw)
        for key in ("event_time", "record_time", "created_at"):
            val = memory.get(key)
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                try:
                    return datetime.fromisoformat(val).timestamp()
                except ValueError:
                    continue
        return None

    # ------------------------------------------------------------------
    # 流水线：Cluster (System 1 / System 2)
    # ------------------------------------------------------------------
    async def _cluster(self, memories: list[dict]) -> list[list[dict]]:
        """DeepSeek 驱动的主题聚类。

        System 1(快过程): 基于标签的规则聚类；
        System 2(慢过程): DeepSeek 分析语义相似性。LLM 不可用时退回 System 1。

        Args:
            memories: 候选经历记忆。

        Returns:
            list[list[dict]]: 满足规模约束的聚类列表。
        """
        if not memories:
            return []
        if self._config.enable_system2 and self._llm is not None:
            clusters = await self._cluster_system2(memories)
            if clusters:
                return clusters
        return self._cluster_system1(memories)

    def _cluster_system1(self, memories: list[dict]) -> list[list[dict]]:
        """基于首要标签的快过程规则聚类。

        Args:
            memories: 候选经历记忆。

        Returns:
            list[list[dict]]: 过滤后的聚类列表。
        """
        buckets: dict[str, list[dict]] = {}
        for mem in memories:
            key = self._primary_tag(mem)
            buckets.setdefault(key, []).append(mem)
        return self._normalize_clusters(list(buckets.values()))

    async def _cluster_system2(self, memories: list[dict]) -> list[list[dict]]:
        """DeepSeek 慢过程语义聚类。

        Args:
            memories: 候选经历记忆。

        Returns:
            list[list[dict]]: 过滤后的聚类列表；LLM 失败时为空。
        """
        listing = self._format_memories_for_prompt(memories)
        system = "你是记忆固结专家，负责将零散经历按主题与因果关系聚类。"
        user = (
            f"以下是{len(memories)}条经历记忆，请按主题聚类。\n{listing}\n"
            '只返回JSON: {"clusters": [[索引,...], ...]}，索引从0开始。'
        )
        result = await self._call_llm(system, user)
        if not result:
            return []
        groups = self._extract_index_groups(result, len(memories))
        clusters = [[memories[i] for i in g] for g in groups]
        return self._normalize_clusters(clusters)

    def _normalize_clusters(
        self, clusters: list[list[dict]]
    ) -> list[list[dict]]:
        """对聚类施加规模约束（过滤过小、截断过大）。

        Args:
            clusters: 原始聚类列表。

        Returns:
            list[list[dict]]: 满足 [min_cluster_size, max_cluster_size] 的聚类。
        """
        normalized: list[list[dict]] = []
        for cluster in clusters:
            if len(cluster) < self._config.min_cluster_size:
                continue
            normalized.append(cluster[: self._config.max_cluster_size])
        return normalized

    @staticmethod
    def _extract_index_groups(result: dict, total: int) -> list[list[int]]:
        """从 LLM 结果解析索引分组并做越界过滤。

        Args:
            result: LLM 返回的字典。
            total: 记忆总数（用于越界校验）。

        Returns:
            list[list[int]]: 合法的索引分组。
        """
        raw_groups = result.get("clusters")
        if not isinstance(raw_groups, list):
            return []
        groups: list[list[int]] = []
        for raw in raw_groups:
            if not isinstance(raw, list):
                continue
            valid = sorted({int(i) for i in raw if isinstance(i, (int, float)) and 0 <= int(i) < total})
            if valid:
                groups.append(valid)
        return groups

    # ------------------------------------------------------------------
    # 流水线：Distill (System 1 / System 2)
    # ------------------------------------------------------------------
    async def _distill(self, cluster: list[dict]) -> dict | None:
        """对一个聚类提炼语义知识。

        DeepSeek 核心作用：将一组相关经历抽象、泛化为一条通用知识。
        LLM 不可用或低置信时退回 System 1 规则摘要。

        Args:
            cluster: 同一主题的经历记忆。

        Returns:
            dict | None: 语义条目；不满足最小规模时为 None。
        """
        if len(cluster) < self._config.min_cluster_size:
            return None
        if self._llm is not None:
            entry = await self._distill_system2(cluster)
            if entry is not None:
                return entry
        return self._distill_system1(cluster)

    async def _distill_system2(self, cluster: list[dict]) -> dict | None:
        """DeepSeek 慢过程提炼语义知识。

        Args:
            cluster: 同一主题的经历记忆。

        Returns:
            dict | None: 满足置信阈值的语义条目；否则 None。
        """
        listing = self._format_memories_for_prompt(cluster)
        system = "你是知识提炼专家，从具体经历中归纳通用知识、规律或原则。"
        user = (
            f"根据以下{len(cluster)}条相关经历，提炼出一条通用知识/规律/原则。\n"
            f"{listing}\n"
            '只返回JSON: {"content": "提炼的知识", "tags": ["标签"], '
            '"confidence": 0.0~1.0}。'
        )
        result = await self._call_llm(system, user)
        if not result:
            return None
        return self._build_semantic_entry(result, cluster, source="deepseek")

    def _distill_system1(self, cluster: list[dict]) -> dict:
        """快过程规则摘要（无 LLM 时的降级提炼）。

        Args:
            cluster: 同一主题的经历记忆。

        Returns:
            dict: 由公共标签与内容拼接而成的语义条目。
        """
        tags = self._common_tags(cluster)
        snippets = [str(m.get("content", "")).strip()[:80] for m in cluster[:5]]
        content = (
            f"综合{len(cluster)}条相关经历提炼: "
            + "; ".join(s for s in snippets if s)
        )
        return {
            "content": content,
            "layer": "semantic",
            "tags": tags or ["consolidation"],
            "confidence": 0.5,
            "source": "consolidation",
            "metadata": {"cluster_size": len(cluster), "method": "system1"},
        }

    def _build_semantic_entry(
        self, result: dict, cluster: list[dict], source: str
    ) -> dict | None:
        """从 LLM 结果构造语义条目并执行置信度门槛。

        Args:
            result: LLM 返回字典。
            cluster: 源经历记忆。
            source: 来源标记。

        Returns:
            dict | None: 置信度达标的语义条目；否则 None。
        """
        content = str(result.get("content") or result.get("text") or "").strip()
        if not content:
            return None
        confidence = self._coerce_confidence(result.get("confidence"))
        if confidence < self._config.confidence_threshold:
            return None
        tags = result.get("tags")
        if not isinstance(tags, list) or not tags:
            tags = self._common_tags(cluster) or ["consolidation"]
        return {
            "content": content,
            "layer": "semantic",
            "tags": [str(t) for t in tags],
            "confidence": confidence,
            "source": source,
            "metadata": {"cluster_size": len(cluster), "method": "system2"},
        }

    @staticmethod
    def _coerce_confidence(raw: Any) -> float:
        """将任意置信度输入归一到 [0, 1]。

        Args:
            raw: LLM 返回的原始置信度。

        Returns:
            float: 规范化后的置信度；无法解析时为 0.5。
        """
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, value))

    # ------------------------------------------------------------------
    # 流水线：Gate & Commit
    # ------------------------------------------------------------------
    async def _process_clusters(
        self, clusters: list[list[dict]], report: ConsolidationReport
    ) -> None:
        """对每个聚类执行 提炼→判决→写入 并更新报告计数。

        Args:
            clusters: 聚类列表。
            report: 待累加统计的报告对象。
        """
        for cluster in clusters:
            entry = await self._distill(cluster)
            if entry is None:
                continue
            report.distilled_count += 1
            await self._gate_and_commit(entry, report)

    async def _gate_and_commit(
        self, entry: dict, report: ConsolidationReport
    ) -> None:
        """对单条语义条目判决并按结果写入 L4。

        Args:
            entry: 语义条目。
            report: 待累加统计的报告对象。
        """
        verdict = await self._gate_check(entry)
        if verdict == "reject":
            report.rejected += 1
            return
        if verdict == "downgrade":
            report.downgraded += 1
            return
        report.passed_gate += 1
        if await self._commit(entry):
            report.committed_to_l4 += 1

    async def _gate_check(self, semantic_entry: dict) -> str:
        """QualityGate 判决: pass / reject / downgrade。

        Args:
            semantic_entry: 待判决语义条目。

        Returns:
            str: 判决结果（小写）；gate 缺失或异常时默认 "pass"。
        """
        if self._gate is None:
            return "pass"
        checker = getattr(self._gate, "check", None)
        if checker is None:
            return "pass"
        try:
            result = await self._maybe_await(
                checker(
                    semantic_entry.get("content", ""),
                    "semantic",
                    semantic_entry.get("tags", []),
                    "medium",
                )
            )
        except Exception as exc:
            self._run_errors.append(f"gate判决失败: {exc}")
            return "pass"
        return self._normalize_verdict(result)

    @staticmethod
    def _normalize_verdict(result: Any) -> str:
        """归一化门禁结果为 pass/reject/downgrade。

        Args:
            result: GateResult 或其他形态的判决结果。

        Returns:
            str: 规范化判决；未知形态统一视为 "pass"。
        """
        verdict = getattr(result, "verdict", result)
        text = str(getattr(verdict, "value", verdict)).lower()
        if "reject" in text:
            return "reject"
        if "downgrade" in text:
            return "downgrade"
        return "pass"

    async def _commit(self, semantic_entry: dict) -> bool:
        """写入 L4 semantic 层。

        Args:
            semantic_entry: 通过判决的语义条目。

        Returns:
            bool: 写入是否成功；semantic_core 缺失时返回 False。
        """
        if self._semantic is None:
            return False
        writer = getattr(self._semantic, "write", None)
        if writer is None:
            return False
        try:
            await self._maybe_await(writer(semantic_entry))
            return True
        except Exception as exc:
            self._run_errors.append(f"commit失败: {exc}")
            return False

    # ------------------------------------------------------------------
    # 自进化 & 报告
    # ------------------------------------------------------------------
    def _resolve_batch_size(self, batch_size: int) -> int:
        """根据历史成功率自适应调整 batch_size。

        成功率高时扩大批量以提升吞吐，偏低时收缩以保证质量。

        Args:
            batch_size: 调用方请求的批量。

        Returns:
            int: 生效的批量（关闭自适应或无历史时原样返回）。
        """
        base = batch_size if batch_size > 0 else self._config.default_batch_size
        history = self._config.success_rate_history
        if not self._config.adaptive_batch_size or not history:
            return base
        avg = sum(history[-5:]) / len(history[-5:])
        if avg >= 0.8:
            base = int(base * 1.5)
        elif avg < 0.5:
            base = max(self._config.min_cluster_size, int(base * 0.5))
        return max(1, min(base, 500))

    def _record_evolution(self, report: ConsolidationReport) -> None:
        """记录本次成功率以驱动后续自进化。

        Args:
            report: 已完成统计的报告对象。
        """
        if report.distilled_count > 0:
            self._config.success_rate_history.append(report.success_rate)
            self._config.success_rate_history = (
                self._config.success_rate_history[-50:]
            )

    @staticmethod
    def _finalize_report(
        report: ConsolidationReport, started: datetime
    ) -> None:
        """补全报告的耗时、成功率与结束时间。

        Args:
            report: 待补全的报告对象。
            started: 固结开始时间。
        """
        completed = datetime.now()
        report.completed_at = completed
        report.duration_seconds = (completed - started).total_seconds()
        if report.distilled_count > 0:
            report.success_rate = report.passed_gate / report.distilled_count
        else:
            report.success_rate = 0.0

    def _new_report(
        self, started: datetime, batch_size: int
    ) -> ConsolidationReport:
        """创建初始零值报告。

        Args:
            started: 固结开始时间。
            batch_size: 生效批量。

        Returns:
            ConsolidationReport: 计数全部置零的新报告。
        """
        return ConsolidationReport(
            started_at=started,
            completed_at=started,
            candidates_found=0,
            batch_size=batch_size,
            clusters_formed=0,
            distilled_count=0,
            passed_gate=0,
            rejected=0,
            downgraded=0,
            committed_to_l4=0,
            success_rate=0.0,
            duration_seconds=0.0,
            errors=self._run_errors,
        )

    def _publish_event(self, event_type: str, payload: dict) -> None:
        """发布事件（静默降级）。

        Args:
            event_type: 事件类型标识。
            payload: 事件负载。
        """
        if self._event_bus is None:
            return
        publisher = getattr(self._event_bus, "publish", None)
        if publisher is None:
            return
        try:
            publisher({"type": event_type, "payload": payload})
        except Exception as exc:  # pragma: no cover - 事件发布不阻断主流程
            self._run_errors.append(f"事件发布失败: {exc}")

    # ------------------------------------------------------------------
    # LLM 调用 & 工具
    # ------------------------------------------------------------------
    async def _call_llm(self, system_prompt: str, user_prompt: str) -> dict | None:
        """调用 DeepSeek 大模型并解析为字典。

        兼容 chat 方法的同步/异步两种返回形态。

        Args:
            system_prompt: 系统提示词。
            user_prompt: 用户提示词。

        Returns:
            dict | None: 解析后的结果；不可用或失败时为 None。
        """
        if self._llm is None:
            return None
        chat = getattr(self._llm, "chat", None)
        if chat is None:
            return None
        try:
            result = await self._maybe_await(chat(user_prompt, system_prompt))
        except Exception as exc:
            self._run_errors.append(f"llm调用失败: {exc}")
            return None
        return self._parse_llm_result(result)

    @staticmethod
    def _parse_llm_result(result: Any) -> dict | None:
        """将 LLM 返回归一化为字典。

        Args:
            result: chat 的原始返回（dict 或含 JSON 的字符串）。

        Returns:
            dict | None: 解析得到的字典；失败时为 None。
        """
        if isinstance(result, dict):
            return result
        if isinstance(result, str):
            match = re.search(r"\{.*\}", result, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return {"text": result}
            return {"text": result}
        return None

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        """统一处理同步/异步返回值。

        Args:
            value: 可能是 awaitable 的返回值。

        Returns:
            Any: await 后的结果或原值。
        """
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _primary_tag(memory: dict) -> str:
        """提取记忆的首要标签作为聚类键。

        Args:
            memory: 记忆字典。

        Returns:
            str: 首个标签；无标签时返回 "__untagged__"。
        """
        tags = memory.get("tags")
        if isinstance(tags, list) and tags:
            return str(tags[0])
        return "__untagged__"

    @staticmethod
    def _common_tags(cluster: list[dict]) -> list[str]:
        """计算聚类内记忆的公共标签。

        Args:
            cluster: 同一主题的记忆集合。

        Returns:
            list[str]: 出现在所有成员中的标签（已去重排序）。
        """
        tag_sets: list[set[str]] = []
        for mem in cluster:
            tags = mem.get("tags")
            if isinstance(tags, list) and tags:
                tag_sets.append({str(t) for t in tags})
        if not tag_sets:
            return []
        common = set.intersection(*tag_sets)
        return sorted(common)

    @staticmethod
    def _format_memories_for_prompt(memories: list[dict]) -> str:
        """将记忆列表格式化为带索引的提示词文本。

        Args:
            memories: 记忆集合。

        Returns:
            str: 每行 "[索引] 内容" 的多行文本。
        """
        lines: list[str] = []
        for idx, mem in enumerate(memories):
            content = str(mem.get("content", "")).strip().replace("\n", " ")
            lines.append(f"[{idx}] {content[:120]}")
        return "\n".join(lines)
