# -*- coding: utf-8-sig -*-
"""天机v10.0.1 系统常量  [v10-ready]

全局常量定义，与ICME六层架构和降级SOP对齐。

版本: 1.0.0
"""

from __future__ import annotations

# === ICME六层名称 ===  [v10-ready]
LAYER_SENSORY = "sensory"
LAYER_WORKING = "working"
LAYER_SHORT_TERM = "short_term"
LAYER_EPISODIC = "episodic"
LAYER_SEMANTIC = "semantic"
LAYER_META = "meta"

ALL_LAYERS: list[str] = [
    LAYER_SENSORY,
    LAYER_WORKING,
    LAYER_SHORT_TERM,
    LAYER_EPISODIC,
    LAYER_SEMANTIC,
    LAYER_META,
]

# === 层级容量上限 (bytes) ===  [v10-ready]
LAYER_CAPACITY: dict[str, int] = {
    LAYER_SENSORY: 10 * 1024 * 1024,  # 10MB
    LAYER_WORKING: 50 * 1024 * 1024,  # 50MB
    LAYER_SHORT_TERM: 100 * 1024 * 1024,  # 100MB
    LAYER_EPISODIC: 500 * 1024 * 1024,  # 500MB
    LAYER_SEMANTIC: 2 * 1024 * 1024 * 1024,  # 2GB
    LAYER_META: 100 * 1024 * 1024,  # 100MB
}

# === 固结间隔 (seconds) ===  [v10-ready]
CONSOLIDATION_INTERVAL: dict[str, int] = {
    LAYER_SENSORY: 30,
    LAYER_WORKING: 60,
    LAYER_SHORT_TERM: 120,
    LAYER_EPISODIC: 300,
    LAYER_SEMANTIC: 600,
    LAYER_META: 900,
}

# === 晋升流向 ===  [v10-ready]
PROMOTION_PATH: dict[str, str] = {
    LAYER_SENSORY: LAYER_WORKING,
    LAYER_WORKING: LAYER_SHORT_TERM,
    LAYER_SHORT_TERM: LAYER_EPISODIC,
    LAYER_EPISODIC: LAYER_SEMANTIC,
    LAYER_SEMANTIC: LAYER_META,
    # LAYER_META: 顶端，无上层
}

# === 性能SLA阈值 (ms) ===  [v10-ready]
SLA_REMEMBER_P99 = 50  # 写入P99
SLA_RECALL_P99 = 100  # 检索P99
SLA_TCL_P99 = 20  # TCL归一化P99
SLA_GATE_P99 = 20  # 门禁P99
SLA_AGENT_DISPATCH_P99 = 50  # Agent调度P99

# === 降级阈值 ===  [v10-ready]
DEGRADE_L1_LATENCY = 1500  # P99>1.5s触发L1降级
DEGRADE_L1_ERROR_RATE = 0.05  # 错误率>5%触发L1降级
DEGRADE_L2_UNAVAILABLE = 300  # 不可用>5min触发L2降级
DEGRADE_L3_UNAVAILABLE = 1800  # 不可用>30min触发L3降级

# === QualityGate配置 ===  [v10-ready]
GATE_MIN_CONTENT_LENGTH = 30
GATE_MAX_SIMILARITY = 0.85
GATE_MIN_VALUE_SCORE = 0.3

# === 系统端口 ===  [v10-ready]
DEFAULT_PORT = 8771
LINGJING_PORT = 8772  # 灵境预留

# === 版本信息 ===  [v10-ready]
TIANJI_VERSION = "9.1.0"
TARGET_VERSION = "10.0.1"
