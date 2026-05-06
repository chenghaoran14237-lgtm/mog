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

MOCK_EMAIL = "exam@healthdoc.local"
MOCK_PASSWORD = "Exam@123456"
MOCK_SOURCE = "exam_mock_v1"


@dataclass(frozen=True, slots=True)
class MeasurementSpec:
    name: str
    value_text: str
    value_numeric: float | None
    unit: str | None
    reference_range: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentSpec:
    title: str
    report_date: str
    document_type: str
    document_category: str
    raw_text: str
    measurements: tuple[MeasurementSpec, ...] = ()
    prose_facts: tuple[str, ...] = ()


def seed_mock_exam_data(session: Session, *, reset: bool = False) -> dict:
    user = _upsert_user(session)
    if reset:
        _delete_existing_mock_data(session, user_id=user.id)

    existing_count = _mock_document_count(session, user_id=user.id)
    if existing_count:
        return _summary(session, user_id=user.id)

    for spec in MOCK_DOCUMENTS:
        _create_document(session, user_id=user.id, spec=spec)

    session.commit()
    return _summary(session, user_id=user.id)


def _upsert_user(session: Session) -> User:
    user = session.scalar(select(User).where(User.email == MOCK_EMAIL))
    password_hash = PasswordHasher().hash_password(MOCK_PASSWORD)
    if user is None:
        user = User(email=MOCK_EMAIL, password_hash=password_hash)
        session.add(user)
        session.flush()
    else:
        user.password_hash = password_hash
        session.flush()
    return user


def _delete_existing_mock_data(session: Session, *, user_id: int) -> None:
    record_ids = list(
        session.scalars(select(Record.id).where(Record.user_id == user_id, Record.source == MOCK_SOURCE)).all()
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
    record = Record(user_id=user_id, source=MOCK_SOURCE, status="normalized")
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
        storage_key=f"{MOCK_SOURCE}:{record.id}",
    )
    session.add(record_file)
    session.flush()

    ocr_result = OCRResult(
        record_file_id=record_file.id,
        revision_number=1,
        supersedes_ocr_result_id=None,
        is_current=True,
        provider_name="mock_exam_seed",
        status="completed",
        raw_text=spec.raw_text,
        raw_payload={"source": MOCK_SOURCE, "title": spec.title},
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
                "fact_id": f"{MOCK_SOURCE}_{index}",
                "fact_type": "clinical_context",
                "display_text": fact,
                "matched_text": fact,
                "parser": "mock_exam_seed",
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


def _mock_document_count(session: Session, *, user_id: int) -> int:
    return int(
        session.scalar(
            select(func.count(ExtractedDocument.id))
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source == MOCK_SOURCE)
        )
        or 0
    )


def _summary(session: Session, *, user_id: int) -> dict:
    document_count = _mock_document_count(session, user_id=user_id)
    measurement_count = int(
        session.scalar(
            select(func.count(Measurement.id))
            .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source == MOCK_SOURCE)
        )
        or 0
    )
    version_ids = list(
        session.scalars(
            select(DocumentVersion.id)
            .join(ExtractedDocument, DocumentVersion.document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source == MOCK_SOURCE)
            .order_by(DocumentVersion.report_date.asc(), DocumentVersion.id.asc())
        ).all()
    )
    return {
        "email": MOCK_EMAIL,
        "password": MOCK_PASSWORD,
        "document_count": document_count,
        "measurement_count": measurement_count,
        "document_version_ids": version_ids,
    }


MOCK_DOCUMENTS: tuple[DocumentSpec, ...] = (
    DocumentSpec(
        title="2026-01-05 入职体检基础测量",
        report_date="2026-01-05 08:20:00",
        document_type="physical_exam",
        document_category="structured_metrics",
        raw_text="""报告日期：2026-01-05
身高 172 cm
体重 78.4 kg
BMI 26.5 kg/m2
收缩压 136 mmHg
舒张压 86 mmHg
心率 78 次/分
腰围 91 cm""",
        measurements=(
            MeasurementSpec("身高", "172", 172.0, "cm"),
            MeasurementSpec("体重", "78.4", 78.4, "kg"),
            MeasurementSpec("BMI", "26.5", 26.5, "kg/m2"),
            MeasurementSpec("收缩压", "136", 136.0, "mmHg"),
            MeasurementSpec("舒张压", "86", 86.0, "mmHg"),
            MeasurementSpec("心率", "78", 78.0, "次/分"),
            MeasurementSpec("腰围", "91", 91.0, "cm"),
        ),
    ),
    DocumentSpec(
        title="2026-01-05 血常规与炎症指标",
        report_date="2026-01-05 09:10:00",
        document_type="lab_report",
        document_category="structured_metrics",
        raw_text="""报告日期：2026-01-05
白细胞 WBC 6.8 10^9/L 3.5-9.5
中性粒细胞 NEUT% 61 %
血红蛋白 HGB 141 g/L 130-175
血小板 PLT 238 10^9/L 125-350
C反应蛋白 CRP 3.6 mg/L 0-8""",
        measurements=(
            MeasurementSpec("白细胞", "6.8", 6.8, "10^9/L", "3.5-9.5"),
            MeasurementSpec("中性粒细胞百分比", "61", 61.0, "%"),
            MeasurementSpec("血红蛋白", "141", 141.0, "g/L"),
            MeasurementSpec("血小板", "238", 238.0, "10^9/L"),
            MeasurementSpec("CRP", "3.6", 3.6, "mg/L", "0-8"),
        ),
    ),
    DocumentSpec(
        title="2026-01-05 肝肾功能与血脂",
        report_date="2026-01-05 09:25:00",
        document_type="lab_report",
        document_category="structured_metrics",
        raw_text="""报告日期：2026-01-05
ALT 38 U/L 0-40
AST 29 U/L 0-40
肌酐 Scr 76 umol/L 45-104
尿酸 UA 392 umol/L 208-428
总胆固醇 TC 5.18 mmol/L 0-5.2
低密度脂蛋白 LDL-C 3.31 mmol/L 0-3.4
甘油三酯 TG 1.84 mmol/L 0-1.7""",
        measurements=(
            MeasurementSpec("ALT", "38", 38.0, "U/L", "0-40"),
            MeasurementSpec("AST", "29", 29.0, "U/L", "0-40"),
            MeasurementSpec("肌酐", "76", 76.0, "umol/L"),
            MeasurementSpec("尿酸", "392", 392.0, "umol/L"),
            MeasurementSpec("总胆固醇", "5.18", 5.18, "mmol/L"),
            MeasurementSpec("LDL-C", "3.31", 3.31, "mmol/L"),
            MeasurementSpec("甘油三酯", "1.84", 1.84, "mmol/L"),
        ),
    ),
    DocumentSpec(
        title="2026-02-06 糖代谢复查",
        report_date="2026-02-06 08:00:00",
        document_type="lab_report",
        document_category="structured_metrics",
        raw_text="""报告日期：2026-02-06
空腹血糖 Glucose 6.4 mmol/L 3.9-6.1
糖化血红蛋白 HbA1c 6.1 % 4.0-6.0
空腹胰岛素 INS 12.8 uIU/mL 2.6-24.9
C肽 C-P 2.2 ng/mL 1.1-4.4""",
        measurements=(
            MeasurementSpec("空腹血糖", "6.4", 6.4, "mmol/L", "3.9-6.1"),
            MeasurementSpec("糖化血红蛋白", "6.1", 6.1, "%", "4.0-6.0"),
            MeasurementSpec("空腹胰岛素", "12.8", 12.8, "uIU/mL"),
            MeasurementSpec("C肽", "2.2", 2.2, "ng/mL"),
        ),
    ),
    DocumentSpec(
        title="2026-02-06 尿常规",
        report_date="2026-02-06 08:30:00",
        document_type="lab_report",
        document_category="structured_metrics",
        raw_text="""报告日期：2026-02-06
尿蛋白 0 mg/dL
尿糖 0 mmol/L
尿酮体 0 mmol/L
尿比重 1.020
尿pH 6.0""",
        measurements=(
            MeasurementSpec("尿蛋白", "0", 0.0, "mg/dL"),
            MeasurementSpec("尿糖", "0", 0.0, "mmol/L"),
            MeasurementSpec("尿酮体", "0", 0.0, "mmol/L"),
            MeasurementSpec("尿比重", "1.020", 1.02, None),
            MeasurementSpec("尿pH", "6.0", 6.0, None),
        ),
    ),
    DocumentSpec(
        title="2026-03-08 肝功能血脂复查",
        report_date="2026-03-08 08:40:00",
        document_type="lab_report",
        document_category="structured_metrics",
        raw_text="""报告日期：2026-03-08
ALT 52 U/L 0-40
AST 34 U/L 0-40
GGT 72 U/L 10-60
总胆固醇 TC 5.71 mmol/L 0-5.2
LDL-C 3.78 mmol/L 0-3.4
甘油三酯 TG 2.26 mmol/L 0-1.7
尿酸 UA 431 umol/L 208-428""",
        measurements=(
            MeasurementSpec("ALT", "52", 52.0, "U/L", "0-40"),
            MeasurementSpec("AST", "34", 34.0, "U/L", "0-40"),
            MeasurementSpec("GGT", "72", 72.0, "U/L"),
            MeasurementSpec("总胆固醇", "5.71", 5.71, "mmol/L"),
            MeasurementSpec("LDL-C", "3.78", 3.78, "mmol/L"),
            MeasurementSpec("甘油三酯", "2.26", 2.26, "mmol/L"),
            MeasurementSpec("尿酸", "431", 431.0, "umol/L"),
        ),
    ),
    DocumentSpec(
        title="2026-03-08 血常规炎症复查",
        report_date="2026-03-08 09:00:00",
        document_type="lab_report",
        document_category="structured_metrics",
        raw_text="""报告日期：2026-03-08
白细胞 WBC 10.8 10^9/L 3.5-9.5
中性粒细胞 NEUT% 75 %
血红蛋白 HGB 139 g/L 130-175
血小板 PLT 265 10^9/L 125-350
C反应蛋白 CRP 16.2 mg/L 0-8""",
        measurements=(
            MeasurementSpec("白细胞", "10.8", 10.8, "10^9/L", "3.5-9.5"),
            MeasurementSpec("中性粒细胞百分比", "75", 75.0, "%"),
            MeasurementSpec("血红蛋白", "139", 139.0, "g/L"),
            MeasurementSpec("血小板", "265", 265.0, "10^9/L"),
            MeasurementSpec("CRP", "16.2", 16.2, "mg/L", "0-8"),
        ),
    ),
    DocumentSpec(
        title="2026-03-20 门诊病历摘要",
        report_date="2026-03-20 15:10:00",
        document_type="clinical_note",
        document_category="narrative_context",
        raw_text="""门诊日期：2026-03-20
主诉：近两周餐后困倦、口渴，偶有夜间加餐。
既往史：患者否认糖尿病史，否认长期服用降糖药；父亲有2型糖尿病史。
处理意见：建议控制精制碳水摄入，记录空腹及餐后2小时血糖，三个月后复查糖化血红蛋白和血脂。""",
        prose_facts=("餐后困倦、口渴", "患者否认糖尿病史", "父亲有2型糖尿病史", "建议复查糖化血红蛋白和血脂"),
    ),
    DocumentSpec(
        title="2026-03-30 腹部超声报告",
        report_date="2026-03-30 10:30:00",
        document_type="imaging_report",
        document_category="narrative_context",
        raw_text="""检查日期：2026-03-30
肝脏大小形态尚可，实质回声稍增强，提示轻度脂肪肝可能。
胆囊壁不厚，未见明显结石声像。胰脾双肾未见明显异常。
建议结合肝功能、血脂和体重管理情况随访。""",
        prose_facts=("轻度脂肪肝可能", "胆囊未见明显结石", "建议结合肝功能和血脂随访"),
    ),
    DocumentSpec(
        title="2026-04-10 糖代谢二次复查",
        report_date="2026-04-10 07:50:00",
        document_type="lab_report",
        document_category="structured_metrics",
        raw_text="""报告日期：2026-04-10
空腹血糖 Glucose 7.6 mmol/L 3.9-6.1
糖化血红蛋白 HbA1c 6.7 % 4.0-6.0
餐后2小时血糖 11.3 mmol/L <7.8
空腹胰岛素 INS 16.1 uIU/mL 2.6-24.9
C肽 C-P 2.8 ng/mL 1.1-4.4""",
        measurements=(
            MeasurementSpec("空腹血糖", "7.6", 7.6, "mmol/L", "3.9-6.1"),
            MeasurementSpec("糖化血红蛋白", "6.7", 6.7, "%", "4.0-6.0"),
            MeasurementSpec("餐后2小时血糖", "11.3", 11.3, "mmol/L", "<7.8"),
            MeasurementSpec("空腹胰岛素", "16.1", 16.1, "uIU/mL"),
            MeasurementSpec("C肽", "2.8", 2.8, "ng/mL"),
        ),
    ),
    DocumentSpec(
        title="2026-04-10 肾功能与尿酸",
        report_date="2026-04-10 08:20:00",
        document_type="lab_report",
        document_category="structured_metrics",
        raw_text="""报告日期：2026-04-10
肌酐 Scr 86 umol/L 45-104
尿酸 UA 472 umol/L 208-428
尿素 Urea 5.8 mmol/L 3.1-8.0
估算肾小球滤过率 eGFR 92 ml/min/1.73m2
尿微量白蛋白 24 mg/L 0-30""",
        measurements=(
            MeasurementSpec("肌酐", "86", 86.0, "umol/L"),
            MeasurementSpec("尿酸", "472", 472.0, "umol/L"),
            MeasurementSpec("尿素", "5.8", 5.8, "mmol/L"),
            MeasurementSpec("eGFR", "92", 92.0, "ml/min/1.73m2"),
            MeasurementSpec("尿微量白蛋白", "24", 24.0, "mg/L"),
        ),
    ),
    DocumentSpec(
        title="2026-04-12 复诊记录",
        report_date="2026-04-12 16:00:00",
        document_type="clinical_note",
        document_category="narrative_context",
        raw_text="""复诊日期：2026-04-12
患者反馈近一个月步行量增加，但夜间加餐仍较频繁。
医生评估：空腹血糖和糖化血红蛋白处于持续升高区间，合并尿酸、LDL-C偏高，应优先进行生活方式干预。
建议：4-6周后复查空腹血糖、血脂、尿酸；如出现明显多饮多尿、体重下降或胸闷胸痛，应及时线下就诊。""",
        prose_facts=("夜间加餐仍较频繁", "空腹血糖和糖化血红蛋白持续升高", "建议4-6周后复查"),
    ),
    DocumentSpec(
        title="2026-05-02 血压与体成分复测",
        report_date="2026-05-02 08:15:00",
        document_type="physical_exam",
        document_category="structured_metrics",
        raw_text="""报告日期：2026-05-02
体重 81.2 kg
BMI 27.4 kg/m2
收缩压 142 mmHg
舒张压 92 mmHg
心率 82 次/分
腰围 95 cm
体脂率 28.4 %""",
        measurements=(
            MeasurementSpec("体重", "81.2", 81.2, "kg"),
            MeasurementSpec("BMI", "27.4", 27.4, "kg/m2"),
            MeasurementSpec("收缩压", "142", 142.0, "mmHg"),
            MeasurementSpec("舒张压", "92", 92.0, "mmHg"),
            MeasurementSpec("心率", "82", 82.0, "次/分"),
            MeasurementSpec("腰围", "95", 95.0, "cm"),
            MeasurementSpec("体脂率", "28.4", 28.4, "%"),
        ),
    ),
    DocumentSpec(
        title="2026-05-04 综合生化复查",
        report_date="2026-05-04 08:05:00",
        document_type="lab_report",
        document_category="structured_metrics",
        raw_text="""报告日期：2026-05-04
ALT 66 U/L 0-40
AST 42 U/L 0-40
GGT 88 U/L 10-60
空腹血糖 Glucose 8.2 mmol/L 3.9-6.1
糖化血红蛋白 HbA1c 7.1 % 4.0-6.0
LDL-C 4.05 mmol/L 0-3.4
甘油三酯 TG 2.42 mmol/L 0-1.7
CRP 8.5 mg/L 0-8""",
        measurements=(
            MeasurementSpec("ALT", "66", 66.0, "U/L", "0-40"),
            MeasurementSpec("AST", "42", 42.0, "U/L", "0-40"),
            MeasurementSpec("GGT", "88", 88.0, "U/L"),
            MeasurementSpec("空腹血糖", "8.2", 8.2, "mmol/L", "3.9-6.1"),
            MeasurementSpec("糖化血红蛋白", "7.1", 7.1, "%", "4.0-6.0"),
            MeasurementSpec("LDL-C", "4.05", 4.05, "mmol/L"),
            MeasurementSpec("甘油三酯", "2.42", 2.42, "mmol/L"),
            MeasurementSpec("CRP", "8.5", 8.5, "mg/L", "0-8"),
        ),
    ),
    DocumentSpec(
        title="2026-05-05 健康管理随访记录",
        report_date="2026-05-05 14:25:00",
        document_type="clinical_note",
        document_category="narrative_context",
        raw_text="""随访日期：2026-05-05
营养师记录：患者过去两周应酬饮酒2次，晚餐主食量仍偏多，睡眠时间约6小时。
运动记录：每周步行3次，每次约35分钟，尚未形成稳定力量训练。
随访建议：继续记录家庭血压和空腹血糖，减少含糖饮料，优先复核肝功能、糖代谢、血脂和尿酸。""",
        prose_facts=("应酬饮酒2次", "晚餐主食量仍偏多", "每周步行3次", "建议复核肝功能、糖代谢、血脂和尿酸"),
    ),
)


def main() -> None:
    ensure_database_schema()
    session = SessionLocal()
    try:
        summary = seed_mock_exam_data(session, reset=True)
        print(
            "Seeded mock exam data: "
            f"email={summary['email']} password={summary['password']} "
            f"documents={summary['document_count']} measurements={summary['measurement_count']}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
