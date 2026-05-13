from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.db import SessionLocal
from app.core.schema import ensure_database_schema
from app.models import DocumentVersion, ExtractedDocument, Measurement, OCRResult, Record, RecordFile, User
from app.services.security import PasswordHasher

ADMIN_EMAIL = "admin@qq.com"
ADMIN_PASSWORD = "123123123"
ADMIN_SOURCE = "admin_mock_v1"


@dataclass(frozen=True, slots=True)
class MeasurementSpec:
    name: str
    value_text: str
    value_numeric: float | None
    unit: str | None
    reference_range: str | None = None
    flag: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentSpec:
    title: str
    report_date: str
    document_type: str
    document_category: str
    raw_text: str
    measurements: tuple[MeasurementSpec, ...] = ()
    prose_facts: tuple[str, ...] = ()


def seed_admin_mock_data(session: Session, *, reset: bool = True) -> dict:
    user = _upsert_admin_user(session)
    if reset:
        _delete_existing_admin_mock_data(session, user_id=user.id)

    existing_count = _admin_document_count(session, user_id=user.id)
    if existing_count:
        return _summary(session, user_id=user.id)

    for spec in _build_document_specs():
        _create_document(session, user_id=user.id, spec=spec)

    session.commit()
    return _summary(session, user_id=user.id)


def _upsert_admin_user(session: Session) -> User:
    user = session.scalar(select(User).where(User.email == ADMIN_EMAIL))
    password_hash = PasswordHasher().hash_password(ADMIN_PASSWORD)
    if user is None:
        user = User(email=ADMIN_EMAIL, password_hash=password_hash)
        session.add(user)
        session.flush()
    else:
        user.password_hash = password_hash
        session.flush()
    return user


def _delete_existing_admin_mock_data(session: Session, *, user_id: int) -> None:
    record_ids = list(
        session.scalars(select(Record.id).where(Record.user_id == user_id, Record.source == ADMIN_SOURCE)).all()
    )
    if not record_ids:
        return

    file_ids = list(session.scalars(select(RecordFile.id).where(RecordFile.record_id.in_(record_ids))).all())
    ocr_ids = list(session.scalars(select(OCRResult.id).where(OCRResult.record_file_id.in_(file_ids))).all()) if file_ids else []
    document_ids = list(
        session.scalars(select(ExtractedDocument.id).where(ExtractedDocument.record_id.in_(record_ids))).all()
    )
    version_ids = (
        list(session.scalars(select(DocumentVersion.id).where(DocumentVersion.document_id.in_(document_ids))).all())
        if document_ids
        else []
    )

    if version_ids:
        session.execute(delete(Measurement).where(Measurement.document_version_id.in_(version_ids)))
        session.execute(delete(DocumentVersion).where(DocumentVersion.id.in_(version_ids)))
    if document_ids:
        session.execute(delete(Measurement).where(Measurement.extracted_document_id.in_(document_ids)))
        session.execute(delete(ExtractedDocument).where(ExtractedDocument.id.in_(document_ids)))
    if ocr_ids:
        session.execute(delete(OCRResult).where(OCRResult.id.in_(ocr_ids)))
    if file_ids:
        session.execute(delete(RecordFile).where(RecordFile.id.in_(file_ids)))
    session.execute(delete(Record).where(Record.id.in_(record_ids)))
    session.flush()


def _create_document(session: Session, *, user_id: int, spec: DocumentSpec) -> None:
    report_date = datetime.strptime(spec.report_date, "%Y-%m-%d %H:%M:%S")
    record = Record(user_id=user_id, source=ADMIN_SOURCE, status="normalized")
    session.add(record)
    session.flush()

    record_file = RecordFile(
        record_id=record.id,
        original_filename=f"{spec.title}.txt",
        display_name=spec.title,
        content_type="text/plain",
        size_bytes=len(spec.raw_text.encode("utf-8")),
        content_bytes=spec.raw_text.encode("utf-8"),
        storage_provider="database_inline",
        storage_key=f"{ADMIN_SOURCE}:{record.id}",
    )
    session.add(record_file)
    session.flush()

    ocr_result = OCRResult(
        record_file_id=record_file.id,
        revision_number=1,
        supersedes_ocr_result_id=None,
        is_current=True,
        provider_name="admin_mock_seed",
        status="completed",
        raw_text=spec.raw_text,
        raw_payload={"source": ADMIN_SOURCE, "title": spec.title, "synthetic": True},
    )
    session.add(ocr_result)
    session.flush()

    measurement_payload = [
        {
            "name": item.name,
            "value_text": item.value_text,
            "value_numeric": item.value_numeric,
            "unit": item.unit,
            "reference_range": item.reference_range,
            "flag": item.flag,
            "observed_at": report_date.isoformat(),
        }
        for item in spec.measurements
    ]
    payload = {
        "raw_text": spec.raw_text,
        "report_date": report_date.isoformat(),
        "document_category": spec.document_category,
        "measurement_count": len(measurement_payload),
        "measurements": measurement_payload,
        "prose_facts": [
            {
                "fact_id": f"{ADMIN_SOURCE}_{index}",
                "fact_type": "clinical_context",
                "display_text": fact,
                "matched_text": fact,
                "parser": "admin_mock_seed",
            }
            for index, fact in enumerate(spec.prose_facts, start=1)
        ],
    }

    document = ExtractedDocument(
        ocr_result_id=ocr_result.id,
        current_ocr_result_id=ocr_result.id,
        record_id=record.id,
        record_file_id=record_file.id,
        document_type=spec.document_type,
        document_category=spec.document_category,
        display_name=spec.title,
        status="normalized",
        report_date=report_date,
        normalized_payload=payload,
    )
    session.add(document)
    session.flush()

    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        supersedes_version_id=None,
        is_current=True,
        created_from_ocr_result_id=ocr_result.id,
        snapshot_hash=hashlib.sha256(f"{spec.title}\n{spec.raw_text}".encode("utf-8")).hexdigest(),
        report_date=report_date,
        normalized_payload=payload,
    )
    session.add(version)
    session.flush()

    for item in spec.measurements:
        session.add(
            Measurement(
                extracted_document_id=document.id,
                document_version_id=version.id,
                name=item.name,
                value_text=item.value_text,
                value_numeric=item.value_numeric,
                unit=item.unit,
                observed_at=report_date,
            )
        )


def _admin_document_count(session: Session, *, user_id: int) -> int:
    return int(
        session.scalar(
            select(func.count(ExtractedDocument.id))
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source == ADMIN_SOURCE)
        )
        or 0
    )


def _summary(session: Session, *, user_id: int) -> dict:
    document_count = _admin_document_count(session, user_id=user_id)
    structured_count = int(
        session.scalar(
            select(func.count(ExtractedDocument.id))
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(
                Record.user_id == user_id,
                Record.source == ADMIN_SOURCE,
                ExtractedDocument.document_category == "structured_metrics",
            )
        )
        or 0
    )
    narrative_count = int(
        session.scalar(
            select(func.count(ExtractedDocument.id))
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(
                Record.user_id == user_id,
                Record.source == ADMIN_SOURCE,
                ExtractedDocument.document_category == "narrative_context",
            )
        )
        or 0
    )
    measurement_count = int(
        session.scalar(
            select(func.count(Measurement.id))
            .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source == ADMIN_SOURCE)
        )
        or 0
    )
    version_ids = list(
        session.scalars(
            select(DocumentVersion.id)
            .join(ExtractedDocument, DocumentVersion.document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source == ADMIN_SOURCE)
            .order_by(DocumentVersion.report_date.asc(), DocumentVersion.id.asc())
        ).all()
    )
    return {
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
        "document_count": document_count,
        "structured_count": structured_count,
        "narrative_count": narrative_count,
        "measurement_count": measurement_count,
        "document_version_ids": version_ids,
    }


def _build_document_specs() -> tuple[DocumentSpec, ...]:
    structured_specs = [_structured_document(index, item) for index, item in enumerate(STRUCTURED_PANELS, start=1)]
    narrative_specs = [_narrative_document(index, item) for index, item in enumerate(NARRATIVE_REPORTS, start=1)]
    return tuple(structured_specs + narrative_specs)


def _structured_document(index: int, item: dict) -> DocumentSpec:
    measurements = tuple(
        MeasurementSpec(
            name=row["name"],
            value_text=str(row["value"]),
            value_numeric=float(row["numeric"]) if row.get("numeric") is not None else None,
            unit=row.get("unit"),
            reference_range=row.get("reference"),
            flag=row.get("flag"),
        )
        for row in item["measurements"]
    )
    raw_text = _render_structured_raw_text(
        title=f"{index:02d} {item['title']}",
        report_date=item["report_date"],
        department=item["department"],
        sample_type=item["sample_type"],
        measurements=measurements,
        conclusion=item["conclusion"],
    )
    return DocumentSpec(
        title=f"Admin体检单{index:02d}-{item['title']}",
        report_date=item["report_date"],
        document_type=item["document_type"],
        document_category="structured_metrics",
        raw_text=raw_text,
        measurements=measurements,
    )


def _narrative_document(index: int, item: dict) -> DocumentSpec:
    raw_text = _render_narrative_raw_text(
        title=f"{index:02d} {item['title']}",
        report_date=item["report_date"],
        sections=item["sections"],
    )
    return DocumentSpec(
        title=f"Admin报告单{index:02d}-{item['title']}",
        report_date=item["report_date"],
        document_type=item["document_type"],
        document_category="narrative_context",
        raw_text=raw_text,
        prose_facts=tuple(item["facts"]),
    )


def _render_structured_raw_text(
    *,
    title: str,
    report_date: str,
    department: str,
    sample_type: str,
    measurements: tuple[MeasurementSpec, ...],
    conclusion: str,
) -> str:
    lines = [
        "MOG市第一健康管理中心",
        title,
        "姓名：Admin演示用户    性别：男    年龄：34岁    体检号：ADM-2026-0520",
        f"科室：{department}    标本类型：{sample_type}",
        f"采样时间：{report_date}    报告时间：{report_date}",
        "项目名称 | 结果 | 单位 | 参考范围 | 提示",
    ]
    for row in measurements:
        lines.append(
            f"{row.name} | {row.value_text} | {row.unit or '--'} | {row.reference_range or '--'} | {row.flag or '--'}"
        )
    lines.extend([f"检查结论：{conclusion}", "声明：以上为合成演示数据，仅用于系统功能测试。"])
    return "\n".join(lines)


def _render_narrative_raw_text(*, title: str, report_date: str, sections: tuple[tuple[str, str], ...]) -> str:
    lines = [
        "MOG市第一健康管理中心",
        title,
        "姓名：Admin演示用户    性别：男    年龄：34岁    档案号：ADM-2026-0520",
        f"报告时间：{report_date}",
    ]
    for section_title, content in sections:
        lines.append(f"{section_title}：{content}")
    lines.append("声明：以上为合成演示数据，仅用于系统功能测试。")
    return "\n".join(lines)


STRUCTURED_PANELS: tuple[dict, ...] = (
    {
        "title": "基础体格检查",
        "report_date": "2026-05-01 08:10:00",
        "department": "体检科",
        "sample_type": "现场测量",
        "document_type": "physical_exam",
        "conclusion": "体重指数偏高，血压处于临界升高区间，建议结合家庭血压记录复核。",
        "measurements": [
            {"name": "身高", "value": "176", "numeric": 176, "unit": "cm", "reference": "--"},
            {"name": "体重", "value": "84.6", "numeric": 84.6, "unit": "kg", "reference": "--", "flag": "偏高"},
            {"name": "BMI", "value": "27.3", "numeric": 27.3, "unit": "kg/m2", "reference": "18.5-23.9", "flag": "偏高"},
            {"name": "收缩压", "value": "142", "numeric": 142, "unit": "mmHg", "reference": "90-139", "flag": "偏高"},
            {"name": "舒张压", "value": "88", "numeric": 88, "unit": "mmHg", "reference": "60-89"},
            {"name": "心率", "value": "82", "numeric": 82, "unit": "次/分", "reference": "60-100"},
        ],
    },
    {
        "title": "血常规",
        "report_date": "2026-05-01 08:35:00",
        "department": "检验科",
        "sample_type": "静脉血",
        "document_type": "lab_report",
        "conclusion": "白细胞和CRP轻度升高，建议结合近期症状判断是否存在急性炎症状态。",
        "measurements": [
            {"name": "白细胞", "value": "10.6", "numeric": 10.6, "unit": "10^9/L", "reference": "3.5-9.5", "flag": "偏高"},
            {"name": "中性粒细胞百分比", "value": "74", "numeric": 74, "unit": "%", "reference": "40-75"},
            {"name": "血红蛋白", "value": "146", "numeric": 146, "unit": "g/L", "reference": "130-175"},
            {"name": "血小板", "value": "268", "numeric": 268, "unit": "10^9/L", "reference": "125-350"},
            {"name": "CRP", "value": "11.2", "numeric": 11.2, "unit": "mg/L", "reference": "0-8", "flag": "偏高"},
        ],
    },
    {
        "title": "肝功能",
        "report_date": "2026-05-01 08:50:00",
        "department": "检验科",
        "sample_type": "血清",
        "document_type": "lab_report",
        "conclusion": "ALT、AST、GGT升高，建议复核饮酒、药物和脂肪肝相关因素。",
        "measurements": [
            {"name": "ALT", "value": "68", "numeric": 68, "unit": "U/L", "reference": "0-40", "flag": "偏高"},
            {"name": "AST", "value": "45", "numeric": 45, "unit": "U/L", "reference": "0-40", "flag": "偏高"},
            {"name": "GGT", "value": "92", "numeric": 92, "unit": "U/L", "reference": "10-60", "flag": "偏高"},
            {"name": "总胆红素", "value": "18.4", "numeric": 18.4, "unit": "umol/L", "reference": "5.1-22.2"},
            {"name": "白蛋白", "value": "44.2", "numeric": 44.2, "unit": "g/L", "reference": "40-55"},
        ],
    },
    {
        "title": "肾功能与尿酸",
        "report_date": "2026-05-01 09:05:00",
        "department": "检验科",
        "sample_type": "血清",
        "document_type": "lab_report",
        "conclusion": "尿酸偏高，肾小球滤过率尚可，建议结合饮食、饮酒和肾功能随访。",
        "measurements": [
            {"name": "肌酐", "value": "88", "numeric": 88, "unit": "umol/L", "reference": "45-104"},
            {"name": "尿素", "value": "5.9", "numeric": 5.9, "unit": "mmol/L", "reference": "3.1-8.0"},
            {"name": "尿酸", "value": "486", "numeric": 486, "unit": "umol/L", "reference": "208-428", "flag": "偏高"},
            {"name": "eGFR", "value": "91", "numeric": 91, "unit": "ml/min/1.73m2", "reference": ">90"},
        ],
    },
    {
        "title": "血脂四项",
        "report_date": "2026-05-01 09:20:00",
        "department": "检验科",
        "sample_type": "血清",
        "document_type": "lab_report",
        "conclusion": "LDL-C和甘油三酯升高，需结合体重、血糖和心血管风险综合管理。",
        "measurements": [
            {"name": "总胆固醇", "value": "5.92", "numeric": 5.92, "unit": "mmol/L", "reference": "<5.2", "flag": "偏高"},
            {"name": "LDL-C", "value": "4.12", "numeric": 4.12, "unit": "mmol/L", "reference": "<3.4", "flag": "偏高"},
            {"name": "HDL-C", "value": "1.02", "numeric": 1.02, "unit": "mmol/L", "reference": ">1.0"},
            {"name": "甘油三酯", "value": "2.36", "numeric": 2.36, "unit": "mmol/L", "reference": "<1.7", "flag": "偏高"},
        ],
    },
    {
        "title": "糖代谢",
        "report_date": "2026-05-01 09:35:00",
        "department": "检验科",
        "sample_type": "静脉血",
        "document_type": "lab_report",
        "conclusion": "空腹血糖和HbA1c升高，建议复查并结合既往病史评估糖代谢异常。",
        "measurements": [
            {"name": "空腹血糖", "value": "8.1", "numeric": 8.1, "unit": "mmol/L", "reference": "3.9-6.1", "flag": "偏高"},
            {"name": "糖化血红蛋白", "value": "7.0", "numeric": 7.0, "unit": "%", "reference": "4.0-6.0", "flag": "偏高"},
            {"name": "空腹胰岛素", "value": "17.8", "numeric": 17.8, "unit": "uIU/mL", "reference": "2.6-24.9"},
            {"name": "C肽", "value": "2.9", "numeric": 2.9, "unit": "ng/mL", "reference": "1.1-4.4"},
        ],
    },
    {
        "title": "尿常规",
        "report_date": "2026-05-01 09:50:00",
        "department": "检验科",
        "sample_type": "尿液",
        "document_type": "lab_report",
        "conclusion": "尿糖弱阳性，需结合血糖结果复核。",
        "measurements": [
            {"name": "尿蛋白", "value": "0", "numeric": 0, "unit": "mg/dL", "reference": "阴性"},
            {"name": "尿糖", "value": "1", "numeric": 1, "unit": "+", "reference": "阴性", "flag": "阳性"},
            {"name": "尿酮体", "value": "0", "numeric": 0, "unit": "+", "reference": "阴性"},
            {"name": "尿比重", "value": "1.023", "numeric": 1.023, "unit": None, "reference": "1.005-1.030"},
            {"name": "尿pH", "value": "5.8", "numeric": 5.8, "unit": None, "reference": "5.0-8.0"},
        ],
    },
    {
        "title": "甲状腺功能",
        "report_date": "2026-05-01 10:05:00",
        "department": "检验科",
        "sample_type": "血清",
        "document_type": "lab_report",
        "conclusion": "TSH轻度升高，建议结合症状和游离甲状腺激素随访。",
        "measurements": [
            {"name": "TSH", "value": "5.21", "numeric": 5.21, "unit": "mIU/L", "reference": "0.27-4.20", "flag": "偏高"},
            {"name": "FT3", "value": "4.7", "numeric": 4.7, "unit": "pmol/L", "reference": "3.1-6.8"},
            {"name": "FT4", "value": "15.6", "numeric": 15.6, "unit": "pmol/L", "reference": "12-22"},
            {"name": "TPOAb", "value": "18", "numeric": 18, "unit": "IU/mL", "reference": "0-34"},
        ],
    },
    {
        "title": "电解质",
        "report_date": "2026-05-01 10:20:00",
        "department": "检验科",
        "sample_type": "血清",
        "document_type": "lab_report",
        "conclusion": "电解质基本稳定。",
        "measurements": [
            {"name": "钾", "value": "4.3", "numeric": 4.3, "unit": "mmol/L", "reference": "3.5-5.3"},
            {"name": "钠", "value": "140", "numeric": 140, "unit": "mmol/L", "reference": "137-147"},
            {"name": "氯", "value": "103", "numeric": 103, "unit": "mmol/L", "reference": "99-110"},
            {"name": "钙", "value": "2.31", "numeric": 2.31, "unit": "mmol/L", "reference": "2.11-2.52"},
            {"name": "镁", "value": "0.82", "numeric": 0.82, "unit": "mmol/L", "reference": "0.75-1.02"},
        ],
    },
    {
        "title": "凝血功能",
        "report_date": "2026-05-01 10:35:00",
        "department": "检验科",
        "sample_type": "枸橼酸抗凝血",
        "document_type": "lab_report",
        "conclusion": "凝血指标未见明显异常。",
        "measurements": [
            {"name": "PT", "value": "11.8", "numeric": 11.8, "unit": "s", "reference": "9.8-13.8"},
            {"name": "INR", "value": "1.02", "numeric": 1.02, "unit": None, "reference": "0.8-1.2"},
            {"name": "APTT", "value": "31.4", "numeric": 31.4, "unit": "s", "reference": "25-37"},
            {"name": "纤维蛋白原", "value": "3.1", "numeric": 3.1, "unit": "g/L", "reference": "2.0-4.0"},
        ],
    },
    {
        "title": "心肌酶谱",
        "report_date": "2026-05-01 10:50:00",
        "department": "检验科",
        "sample_type": "血清",
        "document_type": "lab_report",
        "conclusion": "心肌酶谱未见明确急性损伤证据，若有胸痛需结合心电图和肌钙蛋白复核。",
        "measurements": [
            {"name": "CK", "value": "168", "numeric": 168, "unit": "U/L", "reference": "38-174"},
            {"name": "CK-MB", "value": "14", "numeric": 14, "unit": "U/L", "reference": "0-24"},
            {"name": "LDH", "value": "196", "numeric": 196, "unit": "U/L", "reference": "120-250"},
            {"name": "肌钙蛋白T", "value": "0.006", "numeric": 0.006, "unit": "ng/mL", "reference": "<0.014"},
        ],
    },
    {
        "title": "同型半胱氨酸与维生素",
        "report_date": "2026-05-01 11:05:00",
        "department": "检验科",
        "sample_type": "血清",
        "document_type": "lab_report",
        "conclusion": "同型半胱氨酸轻度升高，维生素D不足。",
        "measurements": [
            {"name": "同型半胱氨酸", "value": "18.6", "numeric": 18.6, "unit": "umol/L", "reference": "5-15", "flag": "偏高"},
            {"name": "维生素D", "value": "18.4", "numeric": 18.4, "unit": "ng/mL", "reference": "20-50", "flag": "偏低"},
            {"name": "维生素B12", "value": "438", "numeric": 438, "unit": "pg/mL", "reference": "200-900"},
            {"name": "叶酸", "value": "6.8", "numeric": 6.8, "unit": "ng/mL", "reference": "3.1-17.5"},
        ],
    },
    {
        "title": "肿瘤标志物基础筛查",
        "report_date": "2026-05-01 11:20:00",
        "department": "检验科",
        "sample_type": "血清",
        "document_type": "lab_report",
        "conclusion": "本次肿瘤标志物未见明显异常，不能替代影像和专科评估。",
        "measurements": [
            {"name": "CEA", "value": "2.8", "numeric": 2.8, "unit": "ng/mL", "reference": "0-5"},
            {"name": "AFP", "value": "3.6", "numeric": 3.6, "unit": "ng/mL", "reference": "0-7"},
            {"name": "CA199", "value": "18.2", "numeric": 18.2, "unit": "U/mL", "reference": "0-37"},
            {"name": "CA125", "value": "12.4", "numeric": 12.4, "unit": "U/mL", "reference": "0-35"},
        ],
    },
    {
        "title": "幽门螺杆菌呼气试验",
        "report_date": "2026-05-01 11:35:00",
        "department": "消化检查室",
        "sample_type": "呼气样本",
        "document_type": "lab_report",
        "conclusion": "C13呼气试验阳性，建议消化科结合症状评估。",
        "measurements": [
            {"name": "C13呼气试验DOB", "value": "8.6", "numeric": 8.6, "unit": None, "reference": "<4", "flag": "阳性"},
            {"name": "呼气试验判定", "value": "1", "numeric": 1, "unit": None, "reference": "0=阴性,1=阳性", "flag": "阳性"},
        ],
    },
    {
        "title": "骨代谢",
        "report_date": "2026-05-01 11:50:00",
        "department": "检验科",
        "sample_type": "血清",
        "document_type": "lab_report",
        "conclusion": "骨代谢指标基本平稳，维生素D不足需结合生活方式处理。",
        "measurements": [
            {"name": "血钙", "value": "2.29", "numeric": 2.29, "unit": "mmol/L", "reference": "2.11-2.52"},
            {"name": "血磷", "value": "1.12", "numeric": 1.12, "unit": "mmol/L", "reference": "0.85-1.51"},
            {"name": "碱性磷酸酶", "value": "88", "numeric": 88, "unit": "U/L", "reference": "45-125"},
            {"name": "25羟维生素D", "value": "18.4", "numeric": 18.4, "unit": "ng/mL", "reference": "20-50", "flag": "偏低"},
        ],
    },
    {
        "title": "眼科体检",
        "report_date": "2026-05-01 13:30:00",
        "department": "眼科",
        "sample_type": "现场检查",
        "document_type": "physical_exam",
        "conclusion": "裸眼视力下降，眼压正常，建议结合用眼习惯和屈光检查。",
        "measurements": [
            {"name": "左眼裸眼视力", "value": "0.6", "numeric": 0.6, "unit": None, "reference": ">=1.0", "flag": "偏低"},
            {"name": "右眼裸眼视力", "value": "0.7", "numeric": 0.7, "unit": None, "reference": ">=1.0", "flag": "偏低"},
            {"name": "左眼眼压", "value": "15", "numeric": 15, "unit": "mmHg", "reference": "10-21"},
            {"name": "右眼眼压", "value": "16", "numeric": 16, "unit": "mmHg", "reference": "10-21"},
        ],
    },
    {
        "title": "肺功能简测",
        "report_date": "2026-05-01 13:50:00",
        "department": "肺功能室",
        "sample_type": "呼吸测试",
        "document_type": "physical_exam",
        "conclusion": "肺功能简测基本正常，FEV1/FVC轻度接近下限。",
        "measurements": [
            {"name": "FVC", "value": "4.12", "numeric": 4.12, "unit": "L", "reference": ">3.5"},
            {"name": "FEV1", "value": "3.18", "numeric": 3.18, "unit": "L", "reference": ">2.8"},
            {"name": "FEV1/FVC", "value": "77.2", "numeric": 77.2, "unit": "%", "reference": ">70"},
            {"name": "PEF", "value": "7.6", "numeric": 7.6, "unit": "L/s", "reference": ">6.5"},
        ],
    },
    {
        "title": "心电图数值摘要",
        "report_date": "2026-05-01 14:10:00",
        "department": "心电图室",
        "sample_type": "十二导联心电图",
        "document_type": "physical_exam",
        "conclusion": "窦性心律，PR/QRS/QTc间期未见明显异常。",
        "measurements": [
            {"name": "心率", "value": "78", "numeric": 78, "unit": "次/分", "reference": "60-100"},
            {"name": "PR间期", "value": "156", "numeric": 156, "unit": "ms", "reference": "120-200"},
            {"name": "QRS时限", "value": "92", "numeric": 92, "unit": "ms", "reference": "<120"},
            {"name": "QTc", "value": "418", "numeric": 418, "unit": "ms", "reference": "<440"},
        ],
    },
    {
        "title": "腹部超声数值摘要",
        "report_date": "2026-05-01 14:35:00",
        "department": "超声科",
        "sample_type": "影像测量",
        "document_type": "physical_exam",
        "conclusion": "肝脏回声增强，肝右叶斜径未见明显增大。",
        "measurements": [
            {"name": "肝右叶斜径", "value": "12.8", "numeric": 12.8, "unit": "cm", "reference": "<14"},
            {"name": "胆囊壁厚", "value": "0.25", "numeric": 0.25, "unit": "cm", "reference": "<0.3"},
            {"name": "脾厚", "value": "3.4", "numeric": 3.4, "unit": "cm", "reference": "<4.0"},
            {"name": "门静脉内径", "value": "1.0", "numeric": 1.0, "unit": "cm", "reference": "<1.3"},
        ],
    },
    {
        "title": "复查综合指标",
        "report_date": "2026-05-15 08:30:00",
        "department": "检验科",
        "sample_type": "静脉血",
        "document_type": "lab_report",
        "conclusion": "生活方式干预后血糖和肝酶仍高，建议内分泌和消化方向复核。",
        "measurements": [
            {"name": "空腹血糖", "value": "7.4", "numeric": 7.4, "unit": "mmol/L", "reference": "3.9-6.1", "flag": "偏高"},
            {"name": "糖化血红蛋白", "value": "6.8", "numeric": 6.8, "unit": "%", "reference": "4.0-6.0", "flag": "偏高"},
            {"name": "ALT", "value": "59", "numeric": 59, "unit": "U/L", "reference": "0-40", "flag": "偏高"},
            {"name": "LDL-C", "value": "3.82", "numeric": 3.82, "unit": "mmol/L", "reference": "<3.4", "flag": "偏高"},
            {"name": "尿酸", "value": "452", "numeric": 452, "unit": "umol/L", "reference": "208-428", "flag": "偏高"},
        ],
    },
)


NARRATIVE_REPORTS: tuple[dict, ...] = (
    {
        "title": "体检总评报告",
        "report_date": "2026-05-01 16:00:00",
        "document_type": "health_summary_report",
        "facts": (
            "体重指数偏高",
            "血压临界升高",
            "糖代谢指标升高",
            "肝酶和血脂异常",
        ),
        "sections": (
            ("总评", "本次体检提示体重指数偏高、血压临界升高、糖代谢异常、肝酶升高、血脂异常和尿酸偏高。"),
            ("重点风险", "空腹血糖、HbA1c、ALT、GGT、LDL-C、甘油三酯和尿酸需要结合病史及复查结果综合判断。"),
            ("建议", "建议控制总热量和精制碳水摄入，减少饮酒，增加规律运动，并在4-6周后复查糖代谢、肝功能、血脂和尿酸。"),
        ),
    },
    {
        "title": "门诊病历记录",
        "report_date": "2026-05-03 10:20:00",
        "document_type": "clinical_note",
        "facts": (
            "患者否认既往糖尿病诊断",
            "近期口渴和餐后困倦",
            "父亲有2型糖尿病史",
            "建议记录家庭血糖和血压",
        ),
        "sections": (
            ("主诉", "体检发现血糖升高2天，伴近期口渴、餐后困倦。"),
            ("现病史", "患者近2个月加班较多，晚餐较晚，夜间加餐频繁；否认既往糖尿病诊断，未规律监测血糖。"),
            ("既往史", "否认冠心病、脑卒中病史；父亲有2型糖尿病史。"),
            ("处理意见", "建议记录空腹及餐后2小时血糖，完善内分泌门诊评估，复查HbA1c和尿微量白蛋白。"),
        ),
    },
    {
        "title": "腹部超声报告",
        "report_date": "2026-05-04 09:30:00",
        "document_type": "imaging_report",
        "facts": (
            "肝实质回声增强",
            "轻度脂肪肝可能",
            "胆囊未见明显结石",
        ),
        "sections": (
            ("检查所见", "肝脏大小形态尚可，实质回声稍增强，肝内未见明确占位；胆囊壁不厚，未见明显结石声像。"),
            ("检查结论", "轻度脂肪肝可能。胆囊、胰腺、脾脏、双肾未见明显异常声像。"),
            ("建议", "结合肝功能、血脂、体重和饮酒史随访。"),
        ),
    },
    {
        "title": "心电图报告",
        "report_date": "2026-05-04 10:10:00",
        "document_type": "ecg_report",
        "facts": (
            "窦性心律",
            "未见急性缺血性改变",
            "建议结合症状随访",
        ),
        "sections": (
            ("检查所见", "窦性心律，心率约78次/分，PR间期、QRS时限、QTc未见明显延长。"),
            ("检查结论", "窦性心律，未见明确急性缺血性ST-T改变。"),
            ("建议", "若出现胸闷、胸痛、活动后气短，应及时线下就诊并复查心肌损伤标志物。"),
        ),
    },
    {
        "title": "健康管理随访报告",
        "report_date": "2026-05-20 15:30:00",
        "document_type": "follow_up_report",
        "facts": (
            "夜间加餐减少但运动仍不足",
            "家庭血压偶有升高",
            "复查糖代谢和肝酶仍异常",
            "建议内分泌门诊评估",
        ),
        "sections": (
            ("随访情况", "患者已减少含糖饮料和夜间加餐，但每周中等强度运动不足150分钟；家庭血压偶有超过140/90mmHg。"),
            ("复核重点", "复查结果提示糖代谢、肝酶、LDL-C和尿酸仍异常，需避免仅凭单次结果作诊断性结论。"),
            ("后续计划", "建议内分泌门诊评估糖代谢，消化或肝病方向复核肝酶升高原因，继续记录家庭血压。"),
        ),
    },
)


def main() -> None:
    ensure_database_schema()
    session = SessionLocal()
    try:
        summary = seed_admin_mock_data(session, reset=True)
        print(
            "Seeded admin mock data: "
            f"email={summary['email']} password={summary['password']} "
            f"documents={summary['document_count']} "
            f"structured={summary['structured_count']} narrative={summary['narrative_count']} "
            f"measurements={summary['measurement_count']}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
