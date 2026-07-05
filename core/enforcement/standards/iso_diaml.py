"""ISO DiAML CF映射 — 从enforcement_hook.py提取"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class ISODimension(str, Enum):
    TASK = "Task"
    AUTO_FEEDBACK = "Auto-Feedback"
    ALLO_FEEDBACK = "Allo-Feedback"
    TURN_MANAGEMENT = "Turn Management"
    TIME_MANAGEMENT = "Time Management"
    DISCOURSE_STRUCTURING = "Discourse Structuring"
    CONTACT_MANAGEMENT = "Contact Management"
    TASK_MANAGEMENT = "Task Management"
    OWN_COMMUNICATION = "Own Communication Management"
    PARTNER_COMMUNICATION = "Partner Communication Management"


@dataclass
class ISOAnnotation:
    dimensions: List[str] = field(default_factory=list)
    primary_function: str = ""
    secondary_functions: List[str] = field(default_factory=list)
    qualifiers: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "dimensions": self.dimensions,
            "primary_function": self.primary_function,
            "secondary_functions": self.secondary_functions,
            "qualifiers": self.qualifiers,
            "confidence": self.confidence,
        }


ISO_COMMUNICATION_FUNCTIONS: Dict[str, Dict] = {
    "Inform": {"code": "INFORM", "category": "information_transfer", "description": "说话者向听话者提供信息"},
    "Question": {"code": "QUESTION", "category": "information_transfer", "description": "说话者向听话者请求信息"},
    "Answer": {"code": "ANSWER", "category": "information_transfer", "description": "说话者回应Question提供信息"},
    "Confirm": {"code": "CONFIRM", "category": "information_transfer", "description": "说话者确认或拒绝先前信息"},
    "Disconfirm": {"code": "DISCONFIRM", "category": "information_transfer", "description": "说话者否认先前信息"},
    "Correct": {"code": "CORRECT", "category": "information_transfer", "description": "说话者纠正错误信息"},
    "Agree": {"code": "AGREE", "category": "discussion_management", "description": "说话者表示同意"},
    "Disagree": {"code": "DISAGREE", "category": "discussion_management", "description": "说话者表示不同意"},
    "Accept": {"code": "ACCEPT", "category": "discussion_management", "description": "说话者接受提议或请求"},
    "Decline": {"code": "DECLINE", "category": "discussion_management", "description": "说话者拒绝提议或请求"},
    "Instruct": {"code": "INSTRUCT", "category": "action_discussion", "description": "说话者指示听话者执行动作"},
    "Request": {"code": "REQUEST", "category": "action_discussion", "description": "说话者请求听话者执行动作"},
    "Offer": {"code": "OFFER", "category": "action_discussion", "description": "说话者提议执行动作"},
    "Promise": {"code": "PROMISE", "category": "action_discussion", "description": "说话者承诺未来执行动作"},
    "Suggestion": {"code": "SUGGESTION", "category": "discussion_management", "description": "说话者建议某个方案"},
    "Propositional Question": {"code": "PROP_Q", "category": "information_transfer", "description": "说话者提出需要评估的命题"},
    "Set Question": {"code": "SET_Q", "category": "information_transfer", "description": "说话者请求某个选项集合"},
    "Choice Question": {"code": "CHOICE_Q", "category": "information_transfer", "description": "说话者请求从选项中做出选择"},
    "Positive Feedback": {"code": "POS_FB", "category": "feedback", "description": "说话者给出正面评价"},
    "Negative Feedback": {"code": "NEG_FB", "category": "feedback", "description": "说话者给出负面评价"},
    "Evaluative Feedback": {"code": "EVAL_FB", "category": "feedback", "description": "说话者给出中性评估"},
    "Self-Reflection": {"code": "SELF_REFL", "category": "own_communication", "description": "说话者进行自省反思"},
    "Planning": {"code": "PLANNING", "category": "own_communication", "description": "说话者规划未来行为"},
    "Clarification": {"code": "CLARIFY", "category": "information_transfer", "description": "说话者澄清先前表述"},
    "Self-Expression": {"code": "SELF_EXPR", "category": "own_communication", "description": "说话者表达主观观点"},
    "Elaboration": {"code": "ELABORATE", "category": "information_transfer", "description": "说话者扩展说明"},
    "Summarize": {"code": "SUMMARIZE", "category": "information_transfer", "description": "说话者摘要概括"},
    "Greeting": {"code": "GREETING", "category": "social_obligation", "description": "社交问候"},
    "Thanking": {"code": "THANKING", "category": "social_obligation", "description": "表示感谢"},
    "Apology": {"code": "APOLOGY", "category": "social_obligation", "description": "表示歉意"},
    "Delegation": {"code": "DELEGATE", "category": "partner_communication", "description": "说话者向伙伴委托任务"},
    "Coordination": {"code": "COORDINATE", "category": "partner_communication", "description": "说话者协调多人行为"},
    "Collaboration": {"code": "COLLABORATE", "category": "partner_communication", "description": "说话者发起协作"},
    "Commitment": {"code": "COMMIT", "category": "action_discussion", "description": "说话者做出承诺保证"},
    "Reasoning": {"code": "REASON", "category": "information_transfer", "description": "说话者展示推理过程"},
    "Verification": {"code": "VERIFY", "category": "feedback", "description": "说话者验证/审计"},
}


class DiAMLSerializer:
    @staticmethod
    def to_xml(annotation: "ISOAnnotation", dialogue_id: str = "",
               sender: str = "", addressee: str = "") -> str:
        diml = '<diaml xmlns="http://www.iso.org/diaml/">\n'
        dialogue_attrs = f' xml:id="d{dialogue_id}"' if dialogue_id else ""
        sender_attr = f' sender="#{sender}"' if sender else ""
        addressee_attr = f' addressee="#{addressee}"' if addressee else ""
        diml += f'  <dialogueAct{dialogue_attrs}{sender_attr}{addressee_attr}'
        if annotation.primary_function:
            cf_code = ISO_COMMUNICATION_FUNCTIONS.get(
                annotation.primary_function, {}).get("code", annotation.primary_function.upper())
            diml += f'\n    communicativeFunction="{cf_code}"'
        if annotation.secondary_functions:
            sfs = []
            for sf in annotation.secondary_functions:
                code = ISO_COMMUNICATION_FUNCTIONS.get(sf, {}).get("code", sf.upper())
                sfs.append(code)
            diml += f'\n    secondaryFunctions="{" ".join(sfs)}"'
        if annotation.dimensions:
            dims_str = " ".join(d.replace(" ", "-") for d in annotation.dimensions)
            diml += f'\n    dimensionSet="{dims_str}"'
        qualifier_items = []
        for k, v in annotation.qualifiers.items():
            qualifier_items.append(f'      <qualifier name="{k}" value="{v}"/>')
        if qualifier_items:
            diml += ">\n"
            diml += "\n".join(qualifier_items)
            diml += f'\n    <certainty>{annotation.confidence:.2f}</certainty>'
            diml += "\n  </dialogueAct>\n"
        else:
            diml += f'>\n    <certainty>{annotation.confidence:.2f}</certainty>\n  </dialogueAct>\n'
        diml += '</diaml>'
        return diml

    @staticmethod
    def to_dict(annotation: "ISOAnnotation") -> Dict:
        result = {
            "diaml_version": "ISO-24617-2",
            "primary_function": {},
            "secondary_functions": [],
            "dimensions": [],
            "qualifiers": annotation.qualifiers,
            "confidence": annotation.confidence,
        }
        if annotation.primary_function:
            cf = ISO_COMMUNICATION_FUNCTIONS.get(annotation.primary_function, {})
            result["primary_function"] = {
                "name": annotation.primary_function,
                "code": cf.get("code", ""),
                "category": cf.get("category", ""),
            }
        for sf in annotation.secondary_functions:
            cf = ISO_COMMUNICATION_FUNCTIONS.get(sf, {})
            result["secondary_functions"].append({
                "name": sf, "code": cf.get("code", ""),
                "category": cf.get("category", ""),
            })
        for d in annotation.dimensions:
            result["dimensions"].append({
                "name": d, "dimension_id": d.replace(" ", "-"),
            })
        return result

    @staticmethod
    def lookup_function(function_name: str) -> Optional[Dict]:
        return ISO_COMMUNICATION_FUNCTIONS.get(function_name)

    @staticmethod
    def functions_by_category() -> Dict[str, List[str]]:
        result: Dict[str, List] = {}
        for name, info in ISO_COMMUNICATION_FUNCTIONS.items():
            cat = info["category"]
            if cat not in result:
                result[cat] = []
            result[cat].append(name)
        return result
@dataclass
class PROVTrace:
    entity_id: str = ""
    activity_id: str = ""
    agent_id: str = ""
    was_generated_by: str = ""
    was_derived_from: List[str] = field(default_factory=list)
    used_entities: List[str] = field(default_factory=list)
    was_attributed_to: str = ""
    generation_time: float = field(default_factory=time.time)
    trace_chain: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "activity_id": self.activity_id,
            "agent_id": self.agent_id,
            "was_generated_by": self.was_generated_by,
            "was_derived_from": self.was_derived_from,
            "used_entities": self.used_entities,
            "was_attributed_to": self.was_attributed_to,
            "generation_time": self.generation_time,
            "trace_chain": self.trace_chain,
        }

