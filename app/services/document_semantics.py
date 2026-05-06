from __future__ import annotations

from datetime import datetime
import re

STRUCTURED_METRICS = "structured_metrics"
NARRATIVE_CONTEXT = "narrative_context"

_DATE_LABEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:报告时间|报告日期|检验时间|检查时间|检查日期|采样时间|送检时间|化验日期|日期)[:：\s]*([12]\d{3}[/-]\d{1,2}[/-]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)"),
    re.compile(r"(?:报告时间|报告日期|检验时间|检查时间|检查日期|采样时间|送检时间|化验日期|日期)[:：\s]*([12]\d{3}年\d{1,2}月\d{1,2}日(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)"),
)
_DATE_FALLBACK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"([12]\d{3}[/-]\d{1,2}[/-]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)"),
    re.compile(r"([12]\d{3}年\d{1,2}月\d{1,2}日(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)"),
)
_NARRATIVE_MARKERS = (
    "入院记录",
    "出院记录",
    "出院小结",
    "病程记录",
    "病历",
    "现病史",
    "既往史",
    "体格检查",
    "诊疗经过",
    "治疗经过",
    "门诊病历",
    "住院病历",
    "主诉",
)
_NARRATIVE_TITLE_MARKERS = (
    "出院诊断证明书",
    "出院记录",
    "出院小结",
    "入院记录",
    "病程记录",
    "门诊病历",
    "住院病历",
)
_NARRATIVE_SECTION_MARKERS = (
    "病情摘要",
    "主诉",
    "现病史",
    "既往史",
    "体格检查",
    "入院查体",
    "入院诊断",
    "出院诊断",
    "诊疗经过",
    "治疗经过",
    "出院医嘱",
)
_STRUCTURED_MARKERS = (
    "项目",
    "结果",
    "参考范围",
    "参考值",
    "单位",
    "检验项目",
    "血常规",
    "生化",
    "尿常规",
)
_STRUCTURED_TITLE_MARKERS = (
    "检验报告单",
    "检验报告",
    "化验单",
    "化验报告",
    "检测报告",
)


def parse_datetime_value(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None

    normalized = (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace("T", " ")
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()

    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def extract_report_date(raw_text: str, normalized_payload: dict | None = None) -> datetime | None:
    payload = normalized_payload or {}
    for key in ("report_date", "report_time", "exam_date", "inspection_date", "sample_time", "observed_at"):
        parsed = parse_datetime_value(payload.get(key))
        if parsed is not None:
            return parsed

    for pattern in _DATE_LABEL_PATTERNS:
        match = pattern.search(raw_text)
        if match:
            parsed = parse_datetime_value(match.group(1))
            if parsed is not None:
                return parsed

    if any(marker in raw_text for marker in _STRUCTURED_MARKERS):
        for pattern in _DATE_FALLBACK_PATTERNS:
            match = pattern.search(raw_text)
            if match:
                parsed = parse_datetime_value(match.group(1))
                if parsed is not None:
                    return parsed

    return None


def infer_document_category(
    *,
    raw_text: str,
    measurements: list[dict] | None = None,
    document_type: str | None = None,
    normalized_payload: dict | None = None,
) -> str:
    payload = normalized_payload or {}
    measurement_items = measurements or payload.get("measurements", []) or []
    measurement_count = len(measurement_items)
    doc_type = (document_type or "").lower()
    lowered = raw_text.lower()

    reliable_measurement_count = sum(
        1
        for item in measurement_items
        if isinstance(item, dict)
        and item.get("name")
        and (
            item.get("value_numeric") is not None
            or str(item.get("value_text") or "").strip()
        )
        and (
            str(item.get("unit") or "").strip()
            or str(item.get("reference_range") or "").strip()
        )
    )
    basic_measurement_count = sum(
        1
        for item in measurement_items
        if isinstance(item, dict)
        and item.get("name")
        and (
            item.get("value_numeric") is not None
            or str(item.get("value_text") or "").strip()
        )
    )
    narrative_title_hits = sum(1 for marker in _NARRATIVE_TITLE_MARKERS if marker in raw_text)
    narrative_section_hits = sum(1 for marker in _NARRATIVE_SECTION_MARKERS if marker in raw_text)
    structured_hits = sum(1 for marker in _STRUCTURED_MARKERS if marker in raw_text)
    narrative_hits = sum(1 for marker in _NARRATIVE_MARKERS if marker in raw_text)
    structured_title_hits = sum(1 for marker in _STRUCTURED_TITLE_MARKERS if marker in raw_text)
    has_long_narrative_body = len(raw_text) >= 240 and any(token in raw_text for token in ("。", "；", "，"))
    has_lab_abbreviation = any(
        token in lowered
        for token in (
            "wbc",
            "rbc",
            "hgb",
            "plt",
            "lymph",
            "neut",
            "glucose",
            "hba1c",
            "alt",
            "ast",
            "ldl",
            "hdl",
            "crp",
            "scr",
            "ua",
        )
    )
    nonempty_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    has_equals_style_rows = any("=" in line for line in nonempty_lines)
    has_compact_lab_rows = reliable_measurement_count >= 2 and len(nonempty_lines) <= max(6, reliable_measurement_count + 2)

    if narrative_title_hits >= 1 and (narrative_section_hits >= 1 or has_long_narrative_body):
        return NARRATIVE_CONTEXT
    if narrative_section_hits >= 3:
        return NARRATIVE_CONTEXT
    if narrative_hits >= 2:
        return NARRATIVE_CONTEXT
    if structured_title_hits >= 1 and (structured_hits >= 2 or reliable_measurement_count >= 3 or has_lab_abbreviation):
        return STRUCTURED_METRICS
    if structured_hits >= 3 and narrative_hits == 0:
        return STRUCTURED_METRICS
    if reliable_measurement_count >= 2 and narrative_hits == 0 and narrative_section_hits == 0 and has_equals_style_rows:
        return STRUCTURED_METRICS
    if basic_measurement_count >= 2 and narrative_hits == 0 and narrative_section_hits == 0 and has_equals_style_rows:
        return STRUCTURED_METRICS
    if has_compact_lab_rows and narrative_hits == 0 and narrative_section_hits == 0:
        return STRUCTURED_METRICS
    if reliable_measurement_count >= 5 and narrative_hits == 0 and narrative_section_hits == 0:
        return STRUCTURED_METRICS
    if measurement_count >= 8 and narrative_title_hits == 0 and narrative_section_hits == 0:
        return STRUCTURED_METRICS
    if has_lab_abbreviation and reliable_measurement_count >= 2 and narrative_hits == 0:
        return STRUCTURED_METRICS
    if doc_type in {"clinical_note", "narrative_context"}:
        return NARRATIVE_CONTEXT
    if doc_type in {"lab_report", "structured_metrics"} and narrative_title_hits == 0 and narrative_section_hits == 0:
        return STRUCTURED_METRICS

    return NARRATIVE_CONTEXT


def category_capabilities(category: str | None) -> dict[str, bool]:
    normalized = category or NARRATIVE_CONTEXT
    return {
        "supports_measurements": normalized == STRUCTURED_METRICS,
        "supports_trend_analysis": normalized == STRUCTURED_METRICS,
        "supports_llm_context": normalized in {STRUCTURED_METRICS, NARRATIVE_CONTEXT},
    }
