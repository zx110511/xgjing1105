r"""
TDAF Schema - 天机数字资产格式 v1.0
=====================================
D16: TDAF v1.0 Schema定义 (JSON-LD兼容)
"""

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional, List, Dict
from pathlib import Path


TDAF_CONTEXT = {
    "@context": {
        "tdaf": "https://tianji.memory/schema/tdaf-v1.0#",
        "asset_id": "tdaf:assetId",
        "layer": "tdaf:layer",
        "content": "tdaf:content",
        "content_hash": "tdaf:contentHash",
        "version": "tdaf:version",
        "provenance": "tdaf:provenance",
        "references": "tdaf:references",
        "knowledge_graph": "tdaf:knowledgeGraph",
        "change_log": "tdaf:changeLog",
    }
}

TDAF_V1_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://tianji.memory/schema/tdaf-v1.0.json",
    "title": "Tianji Digital Asset Format v1.0",
    "description": "天机数字资产格式 - JSON-LD兼容的跨平台可移植格式",
    "type": "object",
    "required": ["tdaf_version", "export_timestamp", "asset_manifest"],
    "properties": {
        "@context": {
            "type": "object",
            "description": "JSON-LD上下文"
        },
        "tdaf_version": {
            "type": "string",
            "const": "1.0",
            "description": "TDAF格式版本"
        },
        "export_timestamp": {
            "type": "number",
            "description": "导出时间戳(UNIX)"
        },
        "export_type": {
            "type": "string",
            "enum": ["full", "incremental"],
            "description": "导出类型: 全量或增量"
        },
        "since_timestamp": {
            "type": "number",
            "description": "增量导出的起始时间戳"
        },
        "asset_manifest": {
            "type": "object",
            "required": ["total_assets", "total_size_bytes"],
            "properties": {
                "total_assets": {"type": "integer"},
                "total_size_bytes": {"type": "integer"},
                "by_layer": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"}
                },
                "by_content_type": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"}
                },
                "by_status": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"}
                }
            }
        },
        "assets": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["asset_id", "memory_id", "layer", "content_hash"],
                "properties": {
                    "asset_id": {"type": "string"},
                    "memory_id": {"type": "string"},
                    "layer": {"type": "string"},
                    "content_type": {"type": "string"},
                    "content": {"type": "string"},
                    "content_hash": {"type": "string"},
                    "version": {"type": "integer"},
                    "parent_version_id": {"type": "string"},
                    "provenance": {"type": "object"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "triples": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "subject": {"type": "string"},
                                "predicate": {"type": "string"},
                                "object": {"type": "string"}
                            }
                        }
                    },
                    "references": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "referenced_by": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "status": {"type": "string"},
                    "created_at": {"type": "number"},
                    "updated_at": {"type": "number"}
                }
            }
        },
        "knowledge_graph": {
            "type": "object",
            "properties": {
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                            "type": {"type": "string"},
                            "layer": {"type": "string"}
                        }
                    }
                },
                "edges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string"},
                            "target": {"type": "string"},
                            "predicate": {"type": "string"},
                            "weight": {"type": "number"}
                        }
                    }
                }
            }
        },
        "directory_indexes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "directory_path": {"type": "string"},
                    "total_files": {"type": "integer"},
                    "total_dirs": {"type": "integer"},
                    "content_hash": {"type": "string"},
                    "children": {"type": "array"}
                }
            }
        },
        "change_log": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "change_id": {"type": "string"},
                    "change_type": {"type": "string"},
                    "target_asset_id": {"type": "string"},
                    "diff_summary": {"type": "string"},
                    "timestamp": {"type": "number"},
                    "trigger_source": {"type": "string"}
                }
            }
        }
    }
}


@dataclass
class TDAFManifest:
    total_assets: int = 0
    total_size_bytes: int = 0
    by_layer: Dict[str, int] = field(default_factory=dict)
    by_content_type: Dict[str, int] = field(default_factory=dict)
    by_status: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TDAFDocument:
    tdaf_version: str = "1.0"
    export_timestamp: float = field(default_factory=time.time)
    export_type: str = "full"
    since_timestamp: float = 0.0
    manifest: TDAFManifest = field(default_factory=TDAFManifest)
    assets: List[Dict] = field(default_factory=list)
    knowledge_graph: Dict = field(default_factory=lambda: {"nodes": [], "edges": []})
    directory_indexes: List[Dict] = field(default_factory=list)
    change_log: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "@context": TDAF_CONTEXT["@context"],
            "tdaf_version": self.tdaf_version,
            "export_timestamp": self.export_timestamp,
            "export_type": self.export_type,
            "since_timestamp": self.since_timestamp,
            "asset_manifest": self.manifest.to_dict(),
            "assets": self.assets,
            "knowledge_graph": self.knowledge_graph,
            "directory_indexes": self.directory_indexes,
            "change_log": self.change_log,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class TDAFValidator:
    REQUIRED_TOP_LEVEL = ["tdaf_version", "export_timestamp", "asset_manifest"]
    REQUIRED_ASSET_FIELDS = ["asset_id", "memory_id", "layer", "content_hash"]
    VALID_LAYERS = {"sensory", "working", "short_term", "episodic", "semantic", "meta"}
    VALID_STATUSES = {"active", "superseded", "deleted", "archived"}

    def validate(self, data: dict) -> tuple:
        errors = []

        for field_name in self.REQUIRED_TOP_LEVEL:
            if field_name not in data:
                errors.append(f"Missing required field: {field_name}")

        if "tdaf_version" in data and data["tdaf_version"] != "1.0":
            errors.append(f"Unsupported TDAF version: {data['tdaf_version']}")

        if "asset_manifest" in data:
            manifest = data["asset_manifest"]
            if "total_assets" not in manifest:
                errors.append("asset_manifest missing total_assets")

        if "assets" in data:
            for i, asset in enumerate(data["assets"]):
                for field_name in self.REQUIRED_ASSET_FIELDS:
                    if field_name not in asset:
                        errors.append(f"Asset[{i}] missing required field: {field_name}")
                if "layer" in asset and asset["layer"] not in self.VALID_LAYERS:
                    errors.append(f"Asset[{i}] invalid layer: {asset['layer']}")
                if "status" in asset and asset["status"] not in self.VALID_STATUSES:
                    errors.append(f"Asset[{i}] invalid status: {asset['status']}")

        if "knowledge_graph" in data:
            kg = data["knowledge_graph"]
            if "nodes" not in kg:
                errors.append("knowledge_graph missing nodes")
            if "edges" not in kg:
                errors.append("knowledge_graph missing edges")

        return len(errors) == 0, errors


def validate_tdaf(data: dict) -> tuple:
    validator = TDAFValidator()
    return validator.validate(data)


def create_empty_tdaf(export_type: str = "full", since_timestamp: float = 0.0) -> TDAFDocument:
    return TDAFDocument(
        export_type=export_type,
        since_timestamp=since_timestamp,
    )
