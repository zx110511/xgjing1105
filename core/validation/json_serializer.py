# -*- coding: utf-8-sig -*-
"""天机v10.0.1 JSON序列化策略  [v10-ready]

JSONSerializationStrategy — 实现 ISerializationStrategy 协议的本地序列化：
    - serialize():   将任意对象 JSON 序列化，自动支持
                     datetime / date / dataclass / Enum / set 等自定义类型
    - deserialize(): 将 JSON 字符串/字节反序列化为目标类型，
                     支持 dataclass 类型映射重建

提取/参考来源:
    core/agent_serializer.py 的 AgentServiceDescriptor.to_json / from_dict
    (dataclass 属性 -> JSON 序列化 / JSON 反序列化 -> 重建对象)

架构定位: core/validation/ — 序列化/验证策略插件化子包 (单进程默认实现)
版本: 1.0.0
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass, fields
from datetime import datetime, date
from enum import Enum
from typing import Any

from core.shared.plugin_interface import PluginInfo

# 插件元信息  [v10-ready]
PLUGIN_INFO = PluginInfo(
    name="json_serializer",
    version="1.0.0",
    description="JSON序列化策略",
    category="validation",
    protocols=["ISerializationStrategy"],
)


class _TianjiJSONEncoder(json.JSONEncoder):
    """天机自定义 JSON 编码器  [v10-ready]

    在标准 JSON 编码基础上，额外支持以下非原生可序列化类型：
        - datetime / date  -> ISO 8601 字符串
        - Enum             -> 其 value
        - dataclass 实例    -> asdict() 字典
        - set / frozenset  -> 列表
        - bytes            -> UTF-8 解码字符串 (失败回退 latin-1)
        - 含 to_dict 方法的对象 -> to_dict() 结果
    """

    def default(self, o: Any) -> Any:  # noqa: D401
        """对非原生类型给出可序列化表示。  [v10-ready]

        Args:
            o: 标准编码器无法处理的对象。

        Returns:
            可被 json 序列化的等价对象。
        """
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, Enum):
            return o.value
        if is_dataclass(o) and not isinstance(o, type):
            return asdict(o)
        if isinstance(o, (set, frozenset)):
            return list(o)
        if isinstance(o, bytes):
            try:
                return o.decode("utf-8")
            except UnicodeDecodeError:
                return o.decode("latin-1")
        if hasattr(o, "to_dict") and callable(o.to_dict):
            return o.to_dict()
        return super().default(o)


class JSONSerializationStrategy:
    """JSON序列化策略 (实现 ISerializationStrategy)  [v10-ready]

    本地默认序列化实现，所有数据以 UTF-8 JSON 文本承载，
    单进程内直接编解码。通过 _TianjiJSONEncoder 透明支持
    datetime / dataclass / Enum 等天机常用自定义类型。

    本地实现: 单进程默认。
    远程对应: RemoteSerializationStrategy (灵境高效二进制序列化)。
    """

    def __init__(self, *, ensure_ascii: bool = False, indent: int | None = None) -> None:
        """初始化 JSON 序列化策略。

        Args:
            ensure_ascii: 是否转义为纯 ASCII (默认 False, 保留中文)。
            indent: 缩进空格数；None 时输出紧凑单行。
        """
        self.ensure_ascii = ensure_ascii
        self.indent = indent

    def serialize(self, obj: Any) -> str | bytes:
        """将对象序列化为 JSON 字符串。  [v10-ready]

        Args:
            obj: 任意可经自定义编码器处理的对象。

        Returns:
            JSON 文本字符串。
        """
        return json.dumps(
            obj,
            ensure_ascii=self.ensure_ascii,
            indent=self.indent,
            cls=_TianjiJSONEncoder,
        )

    def deserialize(self, data: str | bytes, target_type: type) -> Any:
        """将 JSON 数据反序列化为目标类型。  [v10-ready]

        解析规则:
            - data 为 bytes 时按 UTF-8 (兼容 BOM) 解码后解析；
            - target_type 为 dataclass 时按字段名映射重建实例
              (忽略多余键，缺失字段交由 dataclass 默认值处理)；
            - 其余情况直接返回解析后的原生对象 (dict/list/...)。

        Args:
            data: JSON 字符串或字节序列。
            target_type: 期望重建的目标类型。

        Returns:
            反序列化后的对象 (dataclass 实例或原生结构)。
        """
        if isinstance(data, bytes):
            text = data.decode("utf-8-sig")
        else:
            text = data
        parsed = json.loads(text)

        if is_dataclass(target_type) and isinstance(parsed, dict):
            field_names = {f.name for f in fields(target_type)}
            kwargs = {k: v for k, v in parsed.items() if k in field_names}
            return target_type(**kwargs)

        return parsed
