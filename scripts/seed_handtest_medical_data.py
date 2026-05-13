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
from app.models import (
    AuditReportEvent,
    AuditReportNodeState,
    AuditReportRun,
    DocumentVersion,
    ExtractedDocument,
    Measurement,
    OCRResult,
    Record,
    RecordFile,
    User,
    UserProfile,
)
from app.services.security import PasswordHasher

HANDTEST_EMAIL = "handtest@healthdoc.local"
HANDTEST_PASSWORD = "Handtest@123456"
HANDTEST_SOURCE = "handtest_medical_mock_v1"


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


def seed_handtest_medical_data(session: Session, *, reset: bool = True) -> dict:
    user = _upsert_user(session)
    if reset:
        _delete_existing_handtest_data(session, user_id=user.id)

    existing_count = _handtest_document_count(session, user_id=user.id)
    if existing_count:
        return _summary(session, user_id=user.id)

    documents = build_mock_documents()
    structured_count = sum(1 for item in documents if item.document_category == "structured_metrics")
    narrative_count = sum(1 for item in documents if item.document_category == "narrative_context")
    if structured_count != 20 or narrative_count != 10:
        raise RuntimeError(f"Unexpected mock document mix: structured={structured_count}, narrative={narrative_count}")

    for spec in documents:
        _create_document(session, user_id=user.id, spec=spec)

    session.commit()
    return _summary(session, user_id=user.id)


def build_mock_documents() -> tuple[DocumentSpec, ...]:
    periods = [
        {
            "date": "2025-01-08",
            "label": "2025年第一季度",
            "weight": 76.8,
            "bmi": 25.9,
            "waist": 90,
            "sbp": 132,
            "dbp": 84,
            "heart_rate": 76,
            "body_fat": 25.8,
            "glucose": 6.1,
            "hba1c": 5.9,
            "pp2h": 8.4,
            "insulin": 11.2,
            "creatinine": 78,
            "egfr": 106,
            "uric_acid": 396,
            "tc": 5.12,
            "tg": 1.82,
            "hdl": 1.05,
            "ldl": 3.18,
            "alt": 32,
            "ast": 24,
            "ggt": 48,
            "wbc": 6.5,
            "neut": 61,
            "hgb": 144,
            "plt": 236,
            "crp": 2.4,
            "urine_protein": "阴性",
            "urine_glucose": "阴性",
            "urine_ketone": "阴性",
        },
        {
            "date": "2025-04-18",
            "label": "2025年第二季度",
            "weight": 78.2,
            "bmi": 26.4,
            "waist": 92,
            "sbp": 138,
            "dbp": 88,
            "heart_rate": 78,
            "body_fat": 26.9,
            "glucose": 6.5,
            "hba1c": 6.2,
            "pp2h": 9.8,
            "insulin": 13.6,
            "creatinine": 82,
            "egfr": 101,
            "uric_acid": 423,
            "tc": 5.45,
            "tg": 2.05,
            "hdl": 1.00,
            "ldl": 3.45,
            "alt": 45,
            "ast": 31,
            "ggt": 62,
            "wbc": 7.1,
            "neut": 63,
            "hgb": 142,
            "plt": 248,
            "crp": 4.8,
            "urine_protein": "阴性",
            "urine_glucose": "阴性",
            "urine_ketone": "阴性",
        },
        {
            "date": "2025-07-21",
            "label": "2025年第三季度",
            "weight": 80.0,
            "bmi": 27.0,
            "waist": 94,
            "sbp": 144,
            "dbp": 92,
            "heart_rate": 81,
            "body_fat": 28.1,
            "glucose": 7.2,
            "hba1c": 6.6,
            "pp2h": 11.2,
            "insulin": 15.8,
            "creatinine": 85,
            "egfr": 96,
            "uric_acid": 458,
            "tc": 5.92,
            "tg": 2.38,
            "hdl": 0.94,
            "ldl": 3.86,
            "alt": 58,
            "ast": 39,
            "ggt": 78,
            "wbc": 9.8,
            "neut": 72,
            "hgb": 140,
            "plt": 266,
            "crp": 9.6,
            "urine_protein": "弱阳性",
            "urine_glucose": "阴性",
            "urine_ketone": "阴性",
        },
        {
            "date": "2025-10-15",
            "label": "2025年第四季度",
            "weight": 79.4,
            "bmi": 26.8,
            "waist": 93,
            "sbp": 140,
            "dbp": 90,
            "heart_rate": 79,
            "body_fat": 27.6,
            "glucose": 6.8,
            "hba1c": 6.5,
            "pp2h": 10.5,
            "insulin": 14.9,
            "creatinine": 84,
            "egfr": 98,
            "uric_acid": 442,
            "tc": 5.70,
            "tg": 2.20,
            "hdl": 0.98,
            "ldl": 3.72,
            "alt": 50,
            "ast": 35,
            "ggt": 70,
            "wbc": 7.6,
            "neut": 66,
            "hgb": 143,
            "plt": 250,
            "crp": 5.2,
            "urine_protein": "阴性",
            "urine_glucose": "弱阳性",
            "urine_ketone": "阴性",
        },
        {
            "date": "2026-01-10",
            "label": "2026年第一季度",
            "weight": 82.1,
            "bmi": 27.7,
            "waist": 96,
            "sbp": 148,
            "dbp": 94,
            "heart_rate": 84,
            "body_fat": 29.3,
            "glucose": 8.1,
            "hba1c": 7.2,
            "pp2h": 12.6,
            "insulin": 17.4,
            "creatinine": 90,
            "egfr": 90,
            "uric_acid": 486,
            "tc": 6.08,
            "tg": 2.68,
            "hdl": 0.90,
            "ldl": 4.18,
            "alt": 72,
            "ast": 48,
            "ggt": 96,
            "wbc": 11.2,
            "neut": 78,
            "hgb": 139,
            "plt": 278,
            "crp": 18.5,
            "urine_protein": "1+",
            "urine_glucose": "2+",
            "urine_ketone": "阴性",
        },
    ]

    documents: list[DocumentSpec] = []
    for period in periods:
        documents.extend(
            [
                _physical_exam_document(period),
                _glucose_renal_document(period),
                _liver_lipid_document(period),
                _blood_urine_document(period),
            ]
        )

    documents.extend(_narrative_documents())
    return tuple(documents)


def _physical_exam_document(period: dict) -> DocumentSpec:
    date = period["date"]
    measurements = (
        _m("身高", 172, "cm", "成人固定身高"),
        _m("体重", period["weight"], "kg", "按体重管理目标评估"),
        _m("BMI", period["bmi"], "kg/m2", "18.5-23.9"),
        _m("腰围", period["waist"], "cm", "男性<90"),
        _m("收缩压 SBP", period["sbp"], "mmHg", "<140"),
        _m("舒张压 DBP", period["dbp"], "mmHg", "<90"),
        _m("心率", period["heart_rate"], "次/分", "60-100"),
        _m("体脂率", period["body_fat"], "%", "10-24"),
    )
    return DocumentSpec(
        title=f"{date} {period['label']} 体格检查单",
        report_date=f"{date} 08:10:00",
        document_type="physical_exam",
        document_category="structured_metrics",
        raw_text=_structured_raw_text(
            title="体格检查单",
            date=date,
            department="健康体检中心",
            measurements=measurements,
            conclusion="体重、腰围和血压需结合后续代谢指标复核。",
        ),
        measurements=measurements,
    )


def _glucose_renal_document(period: dict) -> DocumentSpec:
    date = period["date"]
    measurements = (
        _m("空腹血糖 Glucose", period["glucose"], "mmol/L", "3.9-6.1"),
        _m("糖化血红蛋白 HbA1c", period["hba1c"], "%", "4.0-6.0"),
        _m("餐后2小时血糖 2hPG", period["pp2h"], "mmol/L", "<7.8"),
        _m("空腹胰岛素 INS", period["insulin"], "uIU/mL", "2.6-24.9"),
        _m("肌酐 Scr", period["creatinine"], "umol/L", "45-104"),
        _m("估算肾小球滤过率 eGFR", period["egfr"], "ml/min/1.73m2", ">90"),
        _m("尿酸 UA", period["uric_acid"], "umol/L", "208-428"),
    )
    return DocumentSpec(
        title=f"{date} {period['label']} 糖代谢与肾功能检验单",
        report_date=f"{date} 08:45:00",
        document_type="lab_glucose_renal",
        document_category="structured_metrics",
        raw_text=_structured_raw_text(
            title="糖代谢与肾功能检验单",
            date=date,
            department="检验科",
            measurements=measurements,
            conclusion="糖代谢指标和尿酸用于综合审计代谢风险变化。",
        ),
        measurements=measurements,
    )


def _liver_lipid_document(period: dict) -> DocumentSpec:
    date = period["date"]
    measurements = (
        _m("总胆固醇 TC", period["tc"], "mmol/L", "0-5.2"),
        _m("甘油三酯 TG", period["tg"], "mmol/L", "0-1.7"),
        _m("高密度脂蛋白 HDL-C", period["hdl"], "mmol/L", ">1.0"),
        _m("低密度脂蛋白 LDL-C", period["ldl"], "mmol/L", "0-3.4"),
        _m("谷丙转氨酶 ALT", period["alt"], "U/L", "0-40"),
        _m("谷草转氨酶 AST", period["ast"], "U/L", "0-40"),
        _m("谷氨酰转肽酶 GGT", period["ggt"], "U/L", "10-60"),
    )
    return DocumentSpec(
        title=f"{date} {period['label']} 肝功能与血脂检验单",
        report_date=f"{date} 09:05:00",
        document_type="lab_liver_lipid",
        document_category="structured_metrics",
        raw_text=_structured_raw_text(
            title="肝功能与血脂检验单",
            date=date,
            department="检验科",
            measurements=measurements,
            conclusion="血脂和肝酶指标用于脂肪肝、代谢异常和用药前风险审计。",
        ),
        measurements=measurements,
    )


def _blood_urine_document(period: dict) -> DocumentSpec:
    date = period["date"]
    measurements = (
        _m("白细胞 WBC", period["wbc"], "10^9/L", "3.5-9.5"),
        _m("中性粒细胞 NEUT%", period["neut"], "%", "40-75"),
        _m("血红蛋白 HGB", period["hgb"], "g/L", "130-175"),
        _m("血小板 PLT", period["plt"], "10^9/L", "125-350"),
        _m("C反应蛋白 CRP", period["crp"], "mg/L", "0-8"),
        MeasurementSpec("尿蛋白 PRO", str(period["urine_protein"]), None, None, "阴性"),
        MeasurementSpec("尿糖 GLU", str(period["urine_glucose"]), None, None, "阴性"),
        MeasurementSpec("尿酮体 KET", str(period["urine_ketone"]), None, None, "阴性"),
    )
    return DocumentSpec(
        title=f"{date} {period['label']} 血常规炎症与尿常规检验单",
        report_date=f"{date} 09:25:00",
        document_type="lab_blood_urine",
        document_category="structured_metrics",
        raw_text=_structured_raw_text(
            title="血常规炎症与尿常规检验单",
            date=date,
            department="检验科",
            measurements=measurements,
            conclusion="炎症指标和尿常规用于复核感染、糖尿病相关尿检异常及肾脏风险。",
        ),
        measurements=measurements,
    )


def _narrative_documents() -> tuple[DocumentSpec, ...]:
    return (
        _narrative_doc(
            title="2025-01-09 腹部超声报告",
            report_date="2025-01-09 10:20:00",
            document_type="ultrasound_report",
            raw_text=(
                "检查项目：腹部彩色多普勒超声\n"
                "肝脏大小形态尚可，实质回声稍增强，肝内管道结构显示清晰，提示轻度脂肪肝可能。"
                "胆囊壁不厚，未见明显结石声像。胰腺、脾脏、双肾未见明显异常。"
                "建议结合肝功能、血脂、体重管理情况随访。"
            ),
            prose_facts=("轻度脂肪肝可能", "胆囊未见明显结石", "建议结合肝功能和血脂随访"),
        ),
        _narrative_doc(
            title="2025-02-12 门诊病历摘要",
            report_date="2025-02-12 15:30:00",
            document_type="clinical_note",
            raw_text=(
                "主诉：近两个月偶有餐后困倦、口渴，夜间加餐较频繁。\n"
                "既往史：患者否认糖尿病确诊史，否认长期服用降糖药；父亲有2型糖尿病史。"
                "处理意见：建议控制精制碳水摄入，记录空腹及餐后2小时血糖，三个月后复查糖化血红蛋白和血脂。"
            ),
            prose_facts=("否认糖尿病确诊史", "父亲有2型糖尿病史", "建议复查糖化血红蛋白和血脂"),
        ),
        _narrative_doc(
            title="2025-04-19 颈动脉超声报告",
            report_date="2025-04-19 10:00:00",
            document_type="vascular_ultrasound_report",
            raw_text=(
                "双侧颈动脉内中膜稍增厚，右侧颈动脉分叉处可见小斑块样回声，约4.0mm x 1.5mm，"
                "管腔未见明显狭窄，血流速度未见明显异常。建议结合血脂、血压和生活方式干预情况复查。"
            ),
            prose_facts=("颈动脉内中膜稍增厚", "右侧颈动脉小斑块", "建议结合血脂和血压复查"),
        ),
        _narrative_doc(
            title="2025-05-20 心电图报告",
            report_date="2025-05-20 09:40:00",
            document_type="ecg_report",
            raw_text=(
                "心电图所见：窦性心律，心率约78次/分。部分导联可见轻度ST-T改变，"
                "未见急性心肌缺血特异性改变。建议结合血压、血脂及临床症状随访。"
            ),
            prose_facts=("窦性心律", "轻度ST-T改变", "未见急性心肌缺血特异性改变"),
        ),
        _narrative_doc(
            title="2025-07-22 内分泌门诊复诊记录",
            report_date="2025-07-22 16:10:00",
            document_type="endocrinology_followup",
            raw_text=(
                "复诊记录：患者近三个月体重增加，运动频率下降。空腹血糖、餐后血糖及糖化血红蛋白较前升高，"
                "合并尿酸、LDL-C偏高。医生建议优先进行生活方式干预，必要时转内分泌专科进一步评估。"
            ),
            prose_facts=("体重增加", "血糖和糖化血红蛋白较前升高", "建议内分泌专科评估"),
        ),
        _narrative_doc(
            title="2025-08-16 胸部低剂量CT报告",
            report_date="2025-08-16 11:05:00",
            document_type="ct_report",
            raw_text=(
                "胸部低剂量CT：双肺纹理稍增多，未见明显活动性感染灶。右肺上叶见微小结节影，直径约3mm，"
                "边界尚清。纵隔未见明显肿大淋巴结。建议按年度体检随访。"
            ),
            prose_facts=("未见明显活动性感染灶", "右肺上叶微小结节约3mm", "建议年度随访"),
        ),
        _narrative_doc(
            title="2025-10-16 眼底检查报告",
            report_date="2025-10-16 09:30:00",
            document_type="fundus_report",
            raw_text=(
                "眼底照相：双眼视盘边界清，黄斑区反光可，未见明显出血、渗出及新生血管。"
                "本次未见明确糖尿病视网膜病变表现。建议如血糖持续升高，6-12个月复查眼底。"
            ),
            prose_facts=("未见明确糖尿病视网膜病变", "建议血糖持续升高时复查眼底"),
        ),
        _narrative_doc(
            title="2025-11-28 营养运动评估报告",
            report_date="2025-11-28 14:00:00",
            document_type="lifestyle_assessment",
            raw_text=(
                "营养评估：患者晚餐主食摄入偏多，每周应酬饮酒约2次，含糖饮料摄入未完全停止。"
                "运动评估：每周步行2-3次，每次约25分钟，尚未形成稳定抗阻训练。"
                "建议减少精制碳水，增加蔬菜和优质蛋白，建立每周150分钟中等强度运动计划。"
            ),
            prose_facts=("晚餐主食摄入偏多", "每周饮酒约2次", "运动频率不足"),
        ),
        _narrative_doc(
            title="2026-01-11 腹部超声复查报告",
            report_date="2026-01-11 10:35:00",
            document_type="ultrasound_followup_report",
            raw_text=(
                "腹部超声复查：肝脏实质回声明显增强，后方声衰减较前增加，考虑脂肪肝程度较前加重。"
                "胆囊、胰腺、脾脏及双肾未见明显占位性病变。建议结合肝酶升高、血脂异常和体重变化进行综合管理。"
            ),
            prose_facts=("脂肪肝程度较前加重", "建议结合肝酶和血脂综合管理"),
        ),
        _narrative_doc(
            title="2026-03-05 综合健康管理随访报告",
            report_date="2026-03-05 15:20:00",
            document_type="health_management_followup",
            raw_text=(
                "随访结论：患者近期工作压力较大，饮食记录不完整，体重控制未达预期。"
                "家庭血压多次记录在140/90mmHg以上，空腹血糖多次超过7.0mmol/L。"
                "建议优先复核血糖、糖化血红蛋白、血脂、肝功能、尿酸和尿常规，并将异常结果提交医生评估。"
            ),
            prose_facts=("家庭血压多次超过140/90mmHg", "空腹血糖多次超过7.0mmol/L", "建议复核多项代谢指标"),
        ),
    )


def _narrative_doc(
    *,
    title: str,
    report_date: str,
    document_type: str,
    raw_text: str,
    prose_facts: tuple[str, ...],
) -> DocumentSpec:
    return DocumentSpec(
        title=title,
        report_date=report_date,
        document_type=document_type,
        document_category="narrative_context",
        raw_text=f"患者：程浩然手测样本\n报告日期：{report_date}\n{raw_text}",
        prose_facts=prose_facts,
    )


def _m(name: str, value: float | int, unit: str | None, reference_range: str | None) -> MeasurementSpec:
    return MeasurementSpec(
        name=name,
        value_text=_format_number(value),
        value_numeric=float(value),
        unit=unit,
        reference_range=reference_range,
    )


def _structured_raw_text(
    *,
    title: str,
    date: str,
    department: str,
    measurements: tuple[MeasurementSpec, ...],
    conclusion: str,
) -> str:
    rows = [
        f"{item.name}\t{item.value_text}\t{item.unit or '-'}\t{item.reference_range or '-'}"
        for item in measurements
    ]
    return "\n".join(
        [
            f"{title}",
            "患者：程浩然手测样本",
            f"报告日期：{date}",
            f"科室：{department}",
            "项目\t结果\t单位\t参考范围",
            *rows,
            f"小结：{conclusion}",
        ]
    )


def _upsert_user(session: Session) -> User:
    user = session.scalar(select(User).where(User.email == HANDTEST_EMAIL))
    password_hash = PasswordHasher().hash_password(HANDTEST_PASSWORD)
    if user is None:
        user = User(email=HANDTEST_EMAIL, password_hash=password_hash)
        session.add(user)
        session.flush()
    else:
        user.password_hash = password_hash
        session.flush()

    profile = session.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if profile is None:
        session.add(
            UserProfile(
                user_id=user.id,
                display_name="程浩然手测样本",
                date_of_birth=datetime(1999, 6, 1),
                gender="male",
                preferences={"mock_dataset": HANDTEST_SOURCE, "scenario": "metabolic_audit"},
            )
        )
    else:
        profile.display_name = "程浩然手测样本"
        profile.date_of_birth = datetime(1999, 6, 1)
        profile.gender = "male"
        profile.preferences = {"mock_dataset": HANDTEST_SOURCE, "scenario": "metabolic_audit"}
    session.flush()
    return user


def _delete_existing_handtest_data(session: Session, *, user_id: int) -> None:
    run_ids = list(session.scalars(select(AuditReportRun.id).where(AuditReportRun.user_id == user_id)).all())
    if run_ids:
        session.execute(delete(AuditReportNodeState).where(AuditReportNodeState.run_id.in_(run_ids)))
        session.execute(delete(AuditReportEvent).where(AuditReportEvent.run_id.in_(run_ids)))
        session.execute(delete(AuditReportRun).where(AuditReportRun.id.in_(run_ids)))

    record_ids = list(
        session.scalars(select(Record.id).where(Record.user_id == user_id, Record.source == HANDTEST_SOURCE)).all()
    )
    if not record_ids:
        session.flush()
        return

    file_ids = list(session.scalars(select(RecordFile.id).where(RecordFile.record_id.in_(record_ids))).all())
    ocr_ids = (
        list(session.scalars(select(OCRResult.id).where(OCRResult.record_file_id.in_(file_ids))).all())
        if file_ids
        else []
    )
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
    record = Record(user_id=user_id, source=HANDTEST_SOURCE, status="normalized")
    session.add(record)
    session.flush()

    content_bytes = spec.raw_text.encode("utf-8")
    record_file = RecordFile(
        record_id=record.id,
        original_filename=f"{spec.title}.txt",
        display_name=spec.title,
        content_type="text/plain; charset=utf-8",
        size_bytes=len(content_bytes),
        content_bytes=content_bytes,
        storage_provider="database_inline",
        storage_key=f"{HANDTEST_SOURCE}:{record.id}",
    )
    session.add(record_file)
    session.flush()

    ocr_result = OCRResult(
        record_file_id=record_file.id,
        revision_number=1,
        supersedes_ocr_result_id=None,
        is_current=True,
        provider_name="handtest_mock_seed",
        status="completed",
        raw_text=spec.raw_text,
        raw_payload={
            "source": HANDTEST_SOURCE,
            "title": spec.title,
            "document_type": spec.document_type,
            "seeded_at": datetime.utcnow().isoformat(),
        },
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
        "document_type": spec.document_type,
        "document_category": spec.document_category,
        "measurement_count": len(measurement_payload),
        "measurements": measurement_payload,
        "prose_facts": [
            {
                "fact_id": f"{HANDTEST_SOURCE}_{record.id}_{index}",
                "fact_type": "clinical_context",
                "display_text": fact,
                "matched_text": fact,
                "parser": "handtest_mock_seed",
            }
            for index, fact in enumerate(spec.prose_facts, start=1)
        ],
        "patient": {
            "display_name": "程浩然手测样本",
            "gender": "male",
            "date_of_birth": "1999-06-01",
        },
        "mock_dataset": {
            "source": HANDTEST_SOURCE,
            "scenario": "metabolic_audit",
        },
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


def _handtest_document_count(session: Session, *, user_id: int) -> int:
    return int(
        session.scalar(
            select(func.count(ExtractedDocument.id))
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source == HANDTEST_SOURCE)
        )
        or 0
    )


def _summary(session: Session, *, user_id: int) -> dict:
    version_ids = list(
        session.scalars(
            select(DocumentVersion.id)
            .join(ExtractedDocument, DocumentVersion.document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source == HANDTEST_SOURCE)
            .order_by(DocumentVersion.report_date.asc(), DocumentVersion.id.asc())
        ).all()
    )
    type_rows = session.execute(
        select(ExtractedDocument.document_type, func.count(ExtractedDocument.id))
        .join(Record, ExtractedDocument.record_id == Record.id)
        .where(Record.user_id == user_id, Record.source == HANDTEST_SOURCE)
        .group_by(ExtractedDocument.document_type)
        .order_by(ExtractedDocument.document_type.asc())
    ).all()
    category_rows = session.execute(
        select(ExtractedDocument.document_category, func.count(ExtractedDocument.id))
        .join(Record, ExtractedDocument.record_id == Record.id)
        .where(Record.user_id == user_id, Record.source == HANDTEST_SOURCE)
        .group_by(ExtractedDocument.document_category)
    ).all()
    measurement_count = int(
        session.scalar(
            select(func.count(Measurement.id))
            .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source == HANDTEST_SOURCE)
        )
        or 0
    )
    return {
        "email": HANDTEST_EMAIL,
        "password": HANDTEST_PASSWORD,
        "source": HANDTEST_SOURCE,
        "document_count": len(version_ids),
        "measurement_count": measurement_count,
        "document_version_ids": version_ids,
        "categories": {name: count for name, count in category_rows},
        "types": {name: count for name, count in type_rows},
    }


def _format_number(value: float | int) -> str:
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def main() -> None:
    ensure_database_schema()
    session = SessionLocal()
    try:
        summary = seed_handtest_medical_data(session, reset=True)
        print(
            "Seeded handtest medical data: "
            f"email={summary['email']} password={summary['password']} "
            f"documents={summary['document_count']} measurements={summary['measurement_count']} "
            f"categories={summary['categories']} types={summary['types']}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
