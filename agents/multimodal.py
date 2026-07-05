r"""
天机Multimodal Agent - 多模态感知师 v1.0
========================================================
L1层Agent，负责图像/表格/公式等多模态感知

角色: 万象(@wanxiang) — 多模态感知师
层级: L1
核心能力:
  - 图像理解
  - 表格解析
  - 公式识别
  - 模态分类
  - 统一存储

架构位置: 天机/agents/multimodal.py
依赖: core/knowledge_extractor

灵境道谱溯源: D2-5【多模态感应】· 道二·知枢体道 · 四地煞之知之术
"""

import time
import json
import logging
from typing import Dict, Any, List, Optional
from enum import Enum

from core.orchestration.agent_serializer import AgentSerializable

logger = logging.getLogger(__name__)


class ModalityType(str, Enum):
    IMAGE = "image"
    TABLE = "table"
    EQUATION = "equation"
    AUDIO = "audio"
    TEXT = "text"
    UNKNOWN = "unknown"


class MultimodalAgent(AgentSerializable):
    """
    Multimodal Agent - 多模态感知师 (万象)

    TVP声明:
      [TVP] Agent: @wanxiang | 层级: L1 | 角色: 多模态感知师
      [TVP] 可调用: @yiku (记忆存储), @lianli (知识图谱), @dongcha (上下文)
      [TVP] 协作模式: C-层级 (主控→子协调→工作者)
    """

    AGENT_ID = "wanxiang"
    AGENT_NAME = "万象"
    LAYER = "L1"
    ROLE = "多模态感知师"
    EMOJI = "👁️"

    CAPABILITIES = [
        "图像理解",
        "表格解析",
        "公式识别",
        "模态分类",
        "多模态统一存储"
    ]

    TOOLS = [
        "memory_capture_multimodal",
        "tianji_classify",
        "tianji_extract_knowledge",
        "memory_recall",
        "memory_remember"
    ]

    MCP_SERVER = "memory-engine-global"

    def __init__(self, amim=None, llm_driver=None):
        self.amim = amim
        self.llm_driver = llm_driver

        self._capture_count = 0
        self._modality_stats = {
            ModalityType.IMAGE.value: 0,
            ModalityType.TABLE.value: 0,
            ModalityType.EQUATION.value: 0,
            ModalityType.AUDIO.value: 0,
            ModalityType.TEXT.value: 0
        }

        logger.info(f"[TVP] Agent初始化: @{self.AGENT_ID} ({self.ROLE})")

    def detect_modality(self, content: str, hint: Optional[str] = None) -> ModalityType:
        """
        检测输入模态类型

        Args:
            content: 输入内容
            hint: 用户提示的类型

        Returns:
            检测到的模态类型
        """
        if hint:
            hint_lower = hint.lower()
            if "image" in hint_lower or "图片" in hint_lower:
                return ModalityType.IMAGE
            if "table" in hint_lower or "表格" in hint_lower:
                return ModalityType.TABLE
            if "equation" in hint_lower or "公式" in hint_lower:
                return ModalityType.EQUATION
            if "audio" in hint_lower or "音频" in hint_lower:
                return ModalityType.AUDIO

        content_stripped = content.strip()

        if content_stripped.startswith("data:image/"):
            return ModalityType.IMAGE
        if content_stripped.startswith("|") and "|" in content_stripped[1:]:
            return ModalityType.TABLE
        if "\\" in content_stripped and ("{" in content_stripped or "=" in content_stripped):
            return ModalityType.EQUATION
        if content_stripped.startswith("{") or content_stripped.startswith("["):
            return ModalityType.TEXT

        return ModalityType.TEXT

    def process_image(self, content: str, context: str = "") -> Dict[str, Any]:
        """
        处理图像

        Args:
            content: 图像数据(base64或路径)
            context: 上下文描述

        Returns:
            处理结果
        """
        result = {
            "modality": ModalityType.IMAGE.value,
            "caption": "",
            "entities": [],
            "confidence": 0.0
        }

        if self.llm_driver:
            try:
                prompt = f"描述以下图像的内容，提取关键实体：{context}\n图像已加载，请分析。"
                response = self.llm_driver.generate(prompt, temperature=0.3)
                result["caption"] = response[:500]
                result["confidence"] = 0.85

                entities = self._extract_image_entities(response)
                result["entities"] = entities
            except Exception as e:
                logger.error(f"图像处理失败: {e}")
                result["caption"] = "图像分析失败"
        else:
            result["caption"] = f"图像上下文: {context}" if context else "图像已捕获，待分析"
            result["confidence"] = 0.3

        return result

    def process_table(self, content: str) -> Dict[str, Any]:
        """
        处理表格

        Args:
            content: 表格数据(markdown/csv)

        Returns:
            处理结果
        """
        result = {
            "modality": ModalityType.TABLE.value,
            "headers": [],
            "rows": 0,
            "columns": 0,
            "data": [],
            "summary": "",
            "confidence": 0.0
        }

        try:
            lines = [l.strip() for l in content.strip().split("\n") if l.strip()]

            if "|" in content:
                header_row = None
                for line in lines:
                    if "|" in line:
                        cells = [c.strip() for c in line.split("|") if c.strip()]
                        if not header_row:
                            header_row = cells
                            result["headers"] = cells
                        else:
                            if not all(c.startswith("-") or c.startswith(":") for c in cells if c):
                                result["data"].append(cells)

                result["rows"] = len(result["data"])
                result["columns"] = len(result["headers"])
                result["confidence"] = 0.9 if result["rows"] > 0 else 0.5

                if result["data"]:
                    result["summary"] = f"表格: {result['columns']}列, {result['rows']}行"

            elif "," in content:
                lines_stripped = [l for l in lines if not l.startswith("#")]
                if lines_stripped:
                    result["headers"] = [h.strip() for h in lines_stripped[0].split(",")]
                    result["rows"] = len(lines_stripped) - 1
                    result["columns"] = len(result["headers"])
                    result["confidence"] = 0.85 if result["rows"] > 0 else 0.5
                    result["data"] = [
                        [c.strip() for c in l.split(",")]
                        for l in lines_stripped[1:]
                    ]
                    result["summary"] = f"CSV表格: {result['columns']}列, {result['rows']}行"
        except Exception as e:
            logger.error(f"表格处理失败: {e}")

        return result

    def process_equation(self, content: str) -> Dict[str, Any]:
        """
        处理公式

        Args:
            content: 数学公式(LaTeX)

        Returns:
            处理结果
        """
        result = {
            "modality": ModalityType.EQUATION.value,
            "latex": "",
            "variables": [],
            "description": "",
            "confidence": 0.0
        }

        try:
            result["latex"] = content.strip()

            variables = []
            import re
            var_pattern = r'\\([a-zA-Z]+)\b'
            matches = re.findall(var_pattern, content)
            variables = list(set(matches))
            result["variables"] = variables

            result["confidence"] = 0.8 if variables else 0.5
            result["description"] = f"公式: 包含{len(variables)}个变量" if variables else "公式已捕获"
        except Exception as e:
            logger.error(f"公式处理失败: {e}")

        return result

    def capture(
        self,
        content: str,
        modality_hint: Optional[str] = None,
        context: str = "",
        layer: str = "episodic"
    ) -> Dict[str, Any]:
        """
        多模态捕获

        Args:
            content: 多模态内容
            modality_hint: 模态提示
            context: 上下文
            layer: 存储层

        Returns:
            捕获结果
        """
        start_time = time.time()

        modality = self.detect_modality(content, modality_hint)

        if modality == ModalityType.IMAGE:
            result = self.process_image(content, context)
        elif modality == ModalityType.TABLE:
            result = self.process_table(content)
        elif modality == ModalityType.EQUATION:
            result = self.process_equation(content)
        else:
            result = {
                "modality": ModalityType.TEXT.value,
                "content": content[:500],
                "confidence": 0.7
            }

        self._modality_stats[modality.value] += 1
        self._capture_count += 1

        if self.amim:
            try:
                self.amim.call_tool("memory_remember", {
                    "content": json.dumps(result, ensure_ascii=False),
                    "layer": layer,
                    "tags": [modality.value, "multimodal", f"capture-{self._capture_count}"]
                })
            except Exception as e:
                logger.warning(f"多模态记忆存储失败: {e}")

        return {
            "status": "success",
            "modality": modality.value,
            "result": result,
            "capture_time": time.time() - start_time,
            "total_captures": self._capture_count
        }

    def _extract_image_entities(self, caption: str) -> List[str]:
        """从图像描述中提取实体"""
        import re
        entities = []

        noun_patterns = [
            r'有([一\w]{2,6}(?:个|张|只|条|座|棵|辆|台|件|位))',
            r'([\u4e00-\u9fff]{2,4}(?:人|者|物|器|图|表|卡|页|框))',
            r'看到([\u4e00-\u9fff]{2,10})',
        ]

        for pattern in noun_patterns:
            matches = re.findall(pattern, caption)
            entities.extend(matches)

        return list(set(entities))[:10]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "agent_id": self.AGENT_ID,
            "agent_name": self.AGENT_NAME,
            "layer": self.LAYER,
            "capture_count": self._capture_count,
            "modality_stats": self._modality_stats
        }

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "agent_id": self.AGENT_ID,
            "capture_count": self._capture_count,
            "modalities_supported": [m.value for m in ModalityType]
        }


def memory_capture_multimodal(
    content: str,
    modality_hint: Optional[str] = None,
    context: str = "",
    layer: str = "episodic"
) -> Dict[str, Any]:
    """
    天机多模态捕获MCP工具

    Args:
        content: 多模态内容
        modality_hint: 模态提示
        context: 上下文
        layer: 存储层

    Returns:
        捕获结果
    """
    try:
        agent = MultimodalAgent()
        return agent.capture(content, modality_hint, context, layer)
    except Exception as e:
        logger.error(f"多模态捕获失败: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
