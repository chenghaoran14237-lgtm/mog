from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_chunk import KnowledgeChunk
from app.services.rag_retrieval import rank_knowledge_chunks


DEFAULT_KNOWLEDGE_CHUNKS: list[dict[str, Any]] = [
    {
        "id": "kb-audit-boundary",
        "scope": "medical_audit",
        "source_type": "audit_rule",
        "source_title": "医疗文档审计系统内置规则",
        "section_title": "审计结论边界",
        "content": "综合审计报告用于发现医疗文档质量、指标一致性和证据追溯问题，不直接给出确诊、治愈或用药处方结论。报告应提示需要线下医生结合病史复核。",
        "keywords": ["审计", "非诊断", "安全边界", "复核"],
        "tags": ["safety", "audit"],
        "metadata_json": {"version": "2026.05", "evidence_level": "project_rule"},
    },
    {
        "id": "kb-evidence-traceability",
        "scope": "medical_audit",
        "source_type": "audit_rule",
        "source_title": "医疗文档审计系统内置规则",
        "section_title": "证据追溯要求",
        "content": "风险结论必须绑定可追溯证据，优先引用结构化指标 measurements，其次引用 normalized_payload.raw_text 中的原文片段；没有证据的高风险结论应回到证据补全节点。",
        "keywords": ["证据", "引用", "追溯", "measurements", "raw_text"],
        "tags": ["traceability", "graph"],
        "metadata_json": {"version": "2026.05", "evidence_level": "project_rule"},
    },
    {
        "id": "kb-glucose-review",
        "scope": "medical_audit",
        "source_type": "audit_rule",
        "source_title": "体检指标审计知识库",
        "section_title": "糖代谢指标复核",
        "content": "空腹血糖、随机血糖或 HbA1c 升高时，审计报告应提示结合既往糖尿病史、用药史和复查结果复核；若病历叙述否认糖尿病史但检验结果升高，应作为跨文档一致性复核点。",
        "keywords": ["空腹血糖", "血糖", "glucose", "hba1c", "糖尿病", "复核"],
        "tags": ["lab", "metabolic"],
        "metadata_json": {"version": "2026.05", "evidence_level": "audit_knowledge"},
    },
    {
        "id": "kb-liver-function",
        "scope": "medical_audit",
        "source_type": "audit_rule",
        "source_title": "体检指标审计知识库",
        "section_title": "肝功能指标复核",
        "content": "ALT、AST 或转氨酶升高时，审计报告应提示核对采血日期、饮酒史、用药史、脂肪肝相关描述及后续复查结果，避免仅凭单次异常得出诊断性结论。",
        "keywords": ["ALT", "AST", "谷丙", "转氨酶", "肝功能", "复查"],
        "tags": ["lab", "liver"],
        "metadata_json": {"version": "2026.05", "evidence_level": "audit_knowledge"},
    },
    {
        "id": "kb-inflammatory-markers",
        "scope": "medical_audit",
        "source_type": "audit_rule",
        "source_title": "体检指标审计知识库",
        "section_title": "炎症相关指标复核",
        "content": "CRP、白细胞计数等炎症相关指标异常时，应结合症状、就诊记录和采样时间判断是否存在急性状态；审计结论应描述为需要复核的风险提示。",
        "keywords": ["CRP", "C反应蛋白", "白细胞", "WBC", "炎症", "感染"],
        "tags": ["lab", "infection"],
        "metadata_json": {"version": "2026.05", "evidence_level": "audit_knowledge"},
    },
    {
        "id": "kb-document-quality",
        "scope": "medical_audit",
        "source_type": "audit_rule",
        "source_title": "医疗文档质量审计规则",
        "section_title": "OCR 与报告日期质量",
        "content": "文档缺少 OCR 原文、报告日期或来源文件标识时，应作为文档质量问题记录；这类问题会降低多文档时间线和指标趋势判断的可靠性。",
        "keywords": ["OCR", "报告日期", "原文", "文档质量", "时间线"],
        "tags": ["quality", "ocr"],
        "metadata_json": {"version": "2026.05", "evidence_level": "project_rule"},
    },
    {
        "id": "kb-citation-check",
        "scope": "medical_audit",
        "source_type": "audit_rule",
        "source_title": "LangGraph 审计状态机规则",
        "section_title": "引用校验闭环",
        "content": "引用校验节点发现风险、冲突或一致性结论缺少 evidence_ids 时，应通过 final_router 回到 audit_router，再进入证据补全节点形成闭环。",
        "keywords": ["引用校验", "evidence_ids", "闭环", "final_router", "audit_router"],
        "tags": ["langgraph", "cycle"],
        "metadata_json": {"version": "2026.05", "evidence_level": "project_rule"},
    },
    {
        "id": "kb-report-structure",
        "scope": "medical_audit",
        "source_type": "audit_rule",
        "source_title": "综合审计报告生成规则",
        "section_title": "报告结构",
        "content": "综合审计报告应包含数据来源、文档质量、风险与异常指标、跨文档一致性、知识依据和审计结论，并单独列出证据清单。",
        "keywords": ["综合报告", "报告结构", "知识依据", "证据清单"],
        "tags": ["report", "rag"],
        "metadata_json": {"version": "2026.05", "evidence_level": "project_rule"},
    },
    {
        "id": "msd-diabetes-diagnosis",
        "scope": "medical_audit",
        "source_type": "msd_manual_consumer",
        "source_title": "默沙东诊疗手册大众版：糖尿病",
        "section_title": "糖尿病与血糖复核",
        "content": "默沙东大众版说明，糖尿病与血糖水平过高有关，医生会通过血糖测定诊断，并会结合空腹血糖、糖化血红蛋白或糖耐量试验等结果判断。审计报告遇到空腹血糖或 HbA1c 升高时，应提示复核既往病史、生活方式、用药史和连续监测结果。",
        "keywords": ["糖尿病", "血糖", "空腹血糖", "HbA1c", "糖化血红蛋白", "glucose"],
        "tags": ["msd", "lab", "metabolic"],
        "metadata_json": {
            "source_name": "默沙东诊疗手册大众版",
            "source_url": "https://www.msdmanuals.cn/home/hormonal-and-metabolic-disorders/diabetes-mellitus-and-low-blood-sugar-hypoglycemia/overview-of-diabetes-mellitus",
            "source_language": "zh-CN",
            "source_retrieved_at": "2026-05-08",
            "evidence_level": "public_medical_reference_summary",
        },
    },
    {
        "id": "msd-diabetes-quickfacts",
        "scope": "medical_audit",
        "source_type": "msd_manual_consumer",
        "source_title": "默沙东诊疗手册大众版：小知识 糖尿病",
        "section_title": "血糖自测与 HbA1c 随访",
        "content": "默沙东小知识指出，血糖会受到饮食、活动、压力、感染、药物和一天中时间等因素影响，HbA1c 可反映一段时间内血糖控制情况。审计中不应只依据单次血糖异常作诊断，应提示结合复查和趋势。",
        "keywords": ["血糖自测", "HbA1c", "糖尿病", "复查", "趋势"],
        "tags": ["msd", "follow_up", "metabolic"],
        "metadata_json": {
            "source_name": "默沙东诊疗手册大众版",
            "source_url": "https://www.msdmanuals.cn/home/quick-facts-hormonal-and-metabolic-disorders/diabetes-mellitus-dm-and-disorders-of-blood-sugar-metabolism/diabetes",
            "source_language": "zh-CN",
            "source_retrieved_at": "2026-05-08",
            "evidence_level": "public_medical_reference_summary",
        },
    },
    {
        "id": "msd-liver-blood-tests",
        "scope": "medical_audit",
        "source_type": "msd_manual_consumer",
        "source_title": "默沙东诊疗手册大众版：肝脏血液检测",
        "section_title": "ALT/AST 与肝功能复核",
        "content": "默沙东大众版将 ALT、AST 等肝脏血液检测用于反映肝脏炎症或肝细胞损伤程度，并提示异常原因需要结合病史、影像或进一步检查。审计报告遇到 ALT、AST、GGT 升高时，应提示复核采血时间、饮酒、药物、脂肪肝描述和后续检查。",
        "keywords": ["ALT", "AST", "GGT", "肝功能", "肝脏血液检测", "转氨酶"],
        "tags": ["msd", "lab", "liver"],
        "metadata_json": {
            "source_name": "默沙东诊疗手册大众版",
            "source_url": "https://www.msdmanuals.cn/home/liver-and-gallbladder-disorders/diagnosis-of-liver-gallbladder-and-biliary-disorders/liver-blood-tests?ruleredirectid=14",
            "source_language": "zh-CN",
            "source_retrieved_at": "2026-05-08",
            "evidence_level": "public_medical_reference_summary",
        },
    },
    {
        "id": "msd-hypertension",
        "scope": "medical_audit",
        "source_type": "msd_manual_consumer",
        "source_title": "默沙东诊疗手册大众版：高血压",
        "section_title": "血压测量与高血压复核",
        "content": "默沙东大众版强调高血压诊断需要准确测量，常规评估包括病史、体格检查、心电图、血液检查和尿液检查等。审计中发现收缩压或舒张压升高时，应提示确认测量条件、复测记录、家庭血压和相关肾功能/电解质检查。",
        "keywords": ["高血压", "血压", "收缩压", "舒张压", "mmHg", "心电图"],
        "tags": ["msd", "vital_sign", "cardiovascular"],
        "metadata_json": {
            "source_name": "默沙东诊疗手册大众版",
            "source_url": "https://www.msdmanuals.cn/home/heart-and-blood-vessel-disorders/high-blood-pressure/high-blood-pressure",
            "source_language": "zh-CN",
            "source_retrieved_at": "2026-05-08",
            "evidence_level": "public_medical_reference_summary",
        },
    },
    {
        "id": "msd-wbc-disorders",
        "scope": "medical_audit",
        "source_type": "msd_manual_consumer",
        "source_title": "默沙东诊疗手册大众版：白细胞疾病概述",
        "section_title": "白细胞计数与感染/炎症复核",
        "content": "默沙东大众版说明，白细胞参与机体防御，白细胞过少或过多都可能提示问题；白细胞增多常见于机体对感染的应答，也可见于药物或血液系统疾病。审计中遇到 WBC、CRP 异常，应结合症状、用药、采样时间和病历叙述复核。",
        "keywords": ["白细胞", "WBC", "CRP", "感染", "炎症", "白细胞增多"],
        "tags": ["msd", "lab", "infection"],
        "metadata_json": {
            "source_name": "默沙东诊疗手册大众版",
            "source_url": "https://www.msdmanuals.cn/home/blood-disorders/white-blood-cell-disorders/overview-of-white-blood-cell-disorders",
            "source_language": "zh-CN",
            "source_retrieved_at": "2026-05-08",
            "evidence_level": "public_medical_reference_summary",
        },
    },
    {
        "id": "msd-lipid-levels",
        "scope": "medical_audit",
        "source_type": "msd_manual_consumer",
        "source_title": "默沙东诊疗手册大众版：成人脂质水平的期望值",
        "section_title": "血脂指标复核",
        "content": "默沙东大众版表格列出成人脂质水平的期望范围，包括 LDL 胆固醇、HDL 胆固醇、总胆固醇和甘油三酯。审计报告遇到 LDL-C 或 TG 升高时，应提示结合冠心病、卒中、糖代谢、体重和生活方式等风险因素复核。",
        "keywords": ["血脂", "胆固醇", "LDL-C", "LDL", "HDL", "甘油三酯", "TG"],
        "tags": ["msd", "lab", "lipid"],
        "metadata_json": {
            "source_name": "默沙东诊疗手册大众版",
            "source_url": "https://www.msdmanuals.cn/home/multimedia/table/desirable-lipid-levels-in-adults",
            "source_language": "zh-CN",
            "source_retrieved_at": "2026-05-08",
            "evidence_level": "public_medical_reference_summary",
        },
    },
    {
        "id": "msd-gout-uric-acid",
        "scope": "medical_audit",
        "source_type": "msd_manual_consumer",
        "source_title": "默沙东诊疗手册大众版：小知识 痛风",
        "section_title": "尿酸与痛风风险复核",
        "content": "默沙东大众版介绍，痛风与血液中尿酸水平过高及晶体沉积有关，风险因素包括肾脏问题、饮酒、部分饮食、肥胖和代谢综合征等。审计中发现尿酸升高时，应提示结合肾功能、饮酒饮食、关节症状和既往痛风史复核。",
        "keywords": ["尿酸", "痛风", "高尿酸", "肾脏", "代谢综合征"],
        "tags": ["msd", "lab", "metabolic"],
        "metadata_json": {
            "source_name": "默沙东诊疗手册大众版",
            "source_url": "https://www.msdmanuals.cn/home/quick-facts-bone-joint-and-muscle-disorders/gout/gout",
            "source_language": "zh-CN",
            "source_retrieved_at": "2026-05-08",
            "evidence_level": "public_medical_reference_summary",
        },
    },
    {
        "id": "msd-kidney-function-tests",
        "scope": "medical_audit",
        "source_type": "msd_manual_consumer",
        "source_title": "默沙东诊疗手册大众版：肾功能测定",
        "section_title": "肌酐/eGFR 与肾功能复核",
        "content": "默沙东大众版说明，医生可通过血液或尿液样本评估肾功能，肌酐、肌酐清除率、胱抑素 C 和血尿素氮等可用于辅助判断。审计中遇到肌酐、eGFR 或 BUN 异常，应结合年龄、体重、性别、尿检和慢性病史复核。",
        "keywords": ["肾功能", "肌酐", "eGFR", "BUN", "尿素氮", "胱抑素C"],
        "tags": ["msd", "lab", "kidney"],
        "metadata_json": {
            "source_name": "默沙东诊疗手册大众版",
            "source_url": "https://www.msdmanuals.cn/home/kidney-and-urinary-tract-disorders/diagnosis-of-kidney-disorders/kidney-function-tests",
            "source_language": "zh-CN",
            "source_retrieved_at": "2026-05-08",
            "evidence_level": "public_medical_reference_summary",
        },
    },
    {
        "id": "msd-thyroid-overview",
        "scope": "medical_audit",
        "source_type": "msd_manual_consumer",
        "source_title": "默沙东诊疗手册大众版：小知识 甲状腺概述",
        "section_title": "TSH 与甲状腺功能复核",
        "content": "默沙东大众版介绍，TSH 与甲状腺激素调节相关，甲状腺激素影响代谢、心跳和体温等。审计中发现 TSH、T3 或 T4 异常时，应提示结合症状、复查、用药和内分泌就诊记录复核。",
        "keywords": ["甲状腺", "TSH", "T3", "T4", "内分泌", "代谢"],
        "tags": ["msd", "lab", "thyroid"],
        "metadata_json": {
            "source_name": "默沙东诊疗手册大众版",
            "source_url": "https://www.msdmanuals.cn/home/quick-facts-hormonal-and-metabolic-disorders/thyroid-gland-disorders/overview-of-the-thyroid-gland",
            "source_language": "zh-CN",
            "source_retrieved_at": "2026-05-08",
            "evidence_level": "public_medical_reference_summary",
        },
    },
]


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_active(self, *, scope: str = "medical_audit") -> list[KnowledgeChunk]:
        statement = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.scope == scope, KnowledgeChunk.is_active.is_(True))
            .order_by(KnowledgeChunk.id.asc())
        )
        return list(self.session.scalars(statement).all())

    def ensure_default_chunks(self, *, scope: str = "medical_audit") -> list[KnowledgeChunk]:
        existing = self.list_active(scope=scope)
        if scope != "medical_audit":
            return existing
        existing_by_key = {(item.source_title, item.section_title): item for item in existing}
        missing_chunks = [
            KnowledgeChunk(**_strip_seed_id(item))
            for item in DEFAULT_KNOWLEDGE_CHUNKS
            if (item["source_title"], item["section_title"]) not in existing_by_key
        ]
        changed = False
        for item in DEFAULT_KNOWLEDGE_CHUNKS:
            existing_chunk = existing_by_key.get((item["source_title"], item["section_title"]))
            if existing_chunk is None:
                continue
            if _chunk_needs_update(existing_chunk, item):
                existing_chunk.source_type = item["source_type"]
                existing_chunk.content = item["content"]
                existing_chunk.keywords = list(item["keywords"])
                existing_chunk.tags = list(item["tags"])
                existing_chunk.metadata_json = dict(item["metadata_json"])
                changed = True
        if missing_chunks:
            self.session.add_all(missing_chunks)
            changed = True
        if changed:
            self.session.commit()
        return self.list_active(scope=scope)

    def search(self, *, query: str, top_k: int = 5, scope: str = "medical_audit") -> list[dict[str, Any]]:
        chunks = self.ensure_default_chunks(scope=scope)
        return rank_knowledge_chunks(query, chunks, top_k=top_k)

    def list_source_summaries(self, *, scope: str = "medical_audit") -> list[dict[str, Any]]:
        chunks = self.ensure_default_chunks(scope=scope)
        summaries: dict[tuple[str, str, str], dict[str, Any]] = {}
        for chunk in chunks:
            metadata = chunk.metadata_json or {}
            source_name = metadata.get("source_name") or chunk.source_title
            source_url = metadata.get("source_url") or ""
            key = (source_name, source_url, chunk.source_type)
            item = summaries.setdefault(
                key,
                {
                    "source_name": source_name,
                    "source_url": source_url,
                    "source_type": chunk.source_type,
                    "source_title": chunk.source_title,
                    "source_language": metadata.get("source_language"),
                    "evidence_level": metadata.get("evidence_level"),
                    "source_retrieved_at": metadata.get("source_retrieved_at"),
                    "chunk_count": 0,
                    "sections": [],
                },
            )
            item["chunk_count"] += 1
            if chunk.section_title not in item["sections"]:
                item["sections"].append(chunk.section_title)
        return sorted(
            summaries.values(),
            key=lambda item: (item["source_name"] != "默沙东诊疗手册大众版", item["source_name"], item["source_title"]),
        )


def knowledge_chunk_to_dict(chunk: KnowledgeChunk | dict[str, Any]) -> dict[str, Any]:
    if isinstance(chunk, dict):
        return dict(chunk)
    return {
        "id": chunk.id,
        "scope": chunk.scope,
        "source_type": chunk.source_type,
        "source_title": chunk.source_title,
        "section_title": chunk.section_title,
        "content": chunk.content,
        "keywords": list(chunk.keywords or []),
        "tags": list(chunk.tags or []),
        "metadata_json": dict(chunk.metadata_json or {}),
        "is_active": chunk.is_active,
    }


def _strip_seed_id(item: dict[str, Any]) -> dict[str, Any]:
    payload = dict(item)
    payload.pop("id", None)
    return payload


def _chunk_needs_update(existing: KnowledgeChunk, seed: dict[str, Any]) -> bool:
    return (
        existing.source_type != seed["source_type"]
        or existing.content != seed["content"]
        or list(existing.keywords or []) != list(seed["keywords"])
        or list(existing.tags or []) != list(seed["tags"])
        or dict(existing.metadata_json or {}) != dict(seed["metadata_json"])
    )
