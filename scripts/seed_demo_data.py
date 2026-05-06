from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.schema import ensure_database_schema
from app.models.document_version import DocumentVersion
from app.models.extracted_document import ExtractedDocument
from app.models.measurement import Measurement
from app.models.ocr_result import OCRResult
from app.models.record import Record
from app.models.record_file import RecordFile
from app.models.user import User
from app.services.security import PasswordHasher

DEMO_EMAIL = "demo@healthdoc.local"
DEMO_PASSWORD = "Demo@123456"


LAB_REPORTS = [
    {
        "title": "2026-03-01 血常规与炎症指标",
        "date": "2026-03-01 09:20:00",
        "raw_text": """报告日期：2026-03-01
白细胞 WBC 7.2 10^9/L 3.5-9.5
中性粒细胞百分比 NEUT% 63 %
血红蛋白 HGB 132 g/L 115-150
血小板 PLT 246 10^9/L 125-350
C反应蛋白 CRP 4.2 mg/L 0-8""",
        "measurements": [
            ("白细胞", "7.2", 7.2, "10^9/L"),
            ("中性粒细胞百分比", "63", 63.0, "%"),
            ("血红蛋白", "132", 132.0, "g/L"),
            ("血小板", "246", 246.0, "10^9/L"),
            ("C反应蛋白", "4.2", 4.2, "mg/L"),
        ],
    },
    {
        "title": "2026-03-18 肝肾功能与血脂",
        "date": "2026-03-18 08:45:00",
        "raw_text": """报告日期：2026-03-18
谷丙转氨酶 ALT 46 U/L 0-40
谷草转氨酶 AST 31 U/L 0-40
肌酐 Scr 78 umol/L 45-84
尿酸 UA 426 umol/L 155-357
总胆固醇 TC 5.62 mmol/L 0-5.2
低密度脂蛋白 LDL-C 3.61 mmol/L 0-3.4""",
        "measurements": [
            ("谷丙转氨酶", "46", 46.0, "U/L"),
            ("谷草转氨酶", "31", 31.0, "U/L"),
            ("肌酐", "78", 78.0, "umol/L"),
            ("尿酸", "426", 426.0, "umol/L"),
            ("总胆固醇", "5.62", 5.62, "mmol/L"),
            ("低密度脂蛋白胆固醇", "3.61", 3.61, "mmol/L"),
        ],
    },
    {
        "title": "2026-04-08 空腹血糖与糖化血红蛋白",
        "date": "2026-04-08 07:55:00",
        "raw_text": """报告日期：2026-04-08
空腹血糖 Glucose 6.8 mmol/L 3.9-6.1
糖化血红蛋白 HbA1c 6.4 % 4.0-6.0
胰岛素 INS 13.2 uIU/mL 2.6-24.9
C肽 C-P 2.1 ng/mL 1.1-4.4""",
        "measurements": [
            ("葡萄糖", "6.8", 6.8, "mmol/L"),
            ("糖化血红蛋白", "6.4", 6.4, "%"),
            ("胰岛素", "13.2", 13.2, "uIU/mL"),
            ("C肽", "2.1", 2.1, "ng/mL"),
        ],
    },
]

CLINICAL_NOTES = [
    {
        "title": "2026-03-20 门诊病历摘要",
        "date": "2026-03-20 14:30:00",
        "raw_text": """门诊日期：2026-03-20
主诉：近两周餐后困倦，偶有口渴，无明显胸痛、呼吸困难。
既往史：体检曾提示血脂偏高，家族中父亲有2型糖尿病史。
处理意见：建议控制精制碳水摄入，记录空腹及餐后2小时血糖，三个月后复查糖化血红蛋白和血脂。""",
        "facts": ["餐后困倦和口渴", "父亲有2型糖尿病史", "建议复查糖化血红蛋白和血脂"],
    },
    {
        "title": "2026-03-30 腹部超声报告",
        "date": "2026-03-30 10:10:00",
        "raw_text": """检查日期：2026-03-30
肝脏大小形态尚可，实质回声稍增强，提示轻度脂肪肝可能。
胆囊壁不厚，未见明显结石声像。
脾胰双肾未见明显异常。
建议结合肝功能、血脂和体重管理情况随访。""",
        "facts": ["轻度脂肪肝可能", "胆囊未见明显结石", "建议结合肝功能和血脂随访"],
    },
    {
        "title": "2026-04-12 复诊记录",
        "date": "2026-04-12 16:05:00",
        "raw_text": """复诊日期：2026-04-12
患者反馈近一个月步行量增加，但夜间加餐仍较频繁。
医生评估：空腹血糖和糖化血红蛋白处于临界升高区间，合并尿酸和LDL-C偏高，应优先进行生活方式干预。
建议：4-6周后复查空腹血糖、血脂、尿酸；若出现明显多饮多尿、体重下降或胸闷胸痛，应及时线下就诊。""",
        "facts": ["夜间加餐仍较频繁", "空腹血糖和糖化血红蛋白临界升高", "建议4-6周后复查"],
    },
]


def main() -> None:
    ensure_database_schema()
    session = SessionLocal()
    try:
        user = session.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                password_hash=PasswordHasher().hash_password(DEMO_PASSWORD),
            )
            session.add(user)
            session.flush()
        else:
            user.password_hash = PasswordHasher().hash_password(DEMO_PASSWORD)

        existing = session.scalar(select(Record.id).where(Record.user_id == user.id, Record.source == "demo_mock"))
        if existing is not None:
            session.commit()
            print(f"Demo data already exists for {DEMO_EMAIL}")
            return

        for report in LAB_REPORTS:
            create_document(
                session,
                user_id=user.id,
                title=report["title"],
                date_text=report["date"],
                raw_text=report["raw_text"],
                category="structured_metrics",
                document_type="lab_report",
                measurement_specs=report["measurements"],
                prose_facts=[],
            )

        for note in CLINICAL_NOTES:
            create_document(
                session,
                user_id=user.id,
                title=note["title"],
                date_text=note["date"],
                raw_text=note["raw_text"],
                category="narrative_context",
                document_type="clinical_note",
                measurement_specs=[],
                prose_facts=note["facts"],
            )

        session.commit()
        print(f"Seeded demo data for {DEMO_EMAIL} / {DEMO_PASSWORD}")
    finally:
        session.close()


def create_document(
    session,
    *,
    user_id: int,
    title: str,
    date_text: str,
    raw_text: str,
    category: str,
    document_type: str,
    measurement_specs: list[tuple[str, str, float, str]],
    prose_facts: list[str],
) -> None:
    report_date = datetime.strptime(date_text, "%Y-%m-%d %H:%M:%S")
    record = Record(user_id=user_id, source="demo_mock", status="normalized")
    session.add(record)
    session.flush()

    record_file = RecordFile(
        record_id=record.id,
        original_filename=f"{title}.txt",
        display_name=title,
        content_type="text/plain",
        size_bytes=len(raw_text.encode("utf-8")),
        content_bytes=raw_text.encode("utf-8"),
        storage_provider="database_inline",
        storage_key=None,
    )
    session.add(record_file)
    session.flush()

    ocr_result = OCRResult(
        record_file_id=record_file.id,
        revision_number=1,
        supersedes_ocr_result_id=None,
        is_current=True,
        provider_name="demo_seed",
        status="completed",
        raw_text=raw_text,
        raw_payload={"source": "demo_seed", "title": title},
    )
    session.add(ocr_result)
    session.flush()

    measurement_payload = [
        {
            "name": name,
            "value_text": value_text,
            "value_numeric": value_numeric,
            "unit": unit,
            "observed_at": report_date.isoformat(),
        }
        for name, value_text, value_numeric, unit in measurement_specs
    ]
    payload = {
        "raw_text": raw_text,
        "report_date": report_date.isoformat(),
        "document_category": category,
        "measurement_count": len(measurement_payload),
        "measurements": measurement_payload,
        "prose_facts": [
            {
                "fact_id": f"demo_{index}",
                "fact_type": "clinical_note",
                "display_text": fact,
                "matched_text": fact,
                "parser": "demo_seed",
            }
            for index, fact in enumerate(prose_facts, start=1)
        ],
    }

    document = ExtractedDocument(
        ocr_result_id=ocr_result.id,
        current_ocr_result_id=ocr_result.id,
        record_id=record.id,
        record_file_id=record_file.id,
        document_type=document_type,
        document_category=category,
        display_name=title,
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
        snapshot_hash=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        report_date=report_date,
        normalized_payload=payload,
    )
    session.add(version)
    session.flush()

    for name, value_text, value_numeric, unit in measurement_specs:
        session.add(
            Measurement(
                extracted_document_id=document.id,
                document_version_id=version.id,
                name=name,
                value_text=value_text,
                value_numeric=value_numeric,
                unit=unit,
                observed_at=report_date,
            )
        )


if __name__ == "__main__":
    main()
