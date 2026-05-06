from __future__ import annotations

import re

from app.providers.base import NormalizationProvider, NormalizationResult, ProviderConfig
from app.providers.normalization.metric_canonicalization import canonicalize_metric_name
from app.services.document_semantics import (
    NARRATIVE_CONTEXT,
    STRUCTURED_METRICS,
    category_capabilities,
    extract_report_date,
    infer_document_category,
)

_TABLE_HEADER_MARKERS = (
    "项目",
    "结果",
    "单位",
    "参考",
    "检测方法",
    "检验项目名称",
    "英文名称",
    "椤圭洰",
    "缁撴灉",
    "鍗曚綅",
    "鍙傝€",
    "妫€娴嬫柟娉",
    "妫€楠岄」鐩悕绉",
    "鑻辨枃鍚嶇О",
)
_NON_DATA_MARKERS = (
    "姓名",
    "病历号",
    "病案号",
    "性别",
    "年龄",
    "科别",
    "临床诊断",
    "采样时间",
    "接收时间",
    "报告时间",
    "地址",
    "电话",
    "下载",
    "出院",
    "病情摘要",
    "治疗建议",
    "医师签字",
    "日期",
    "审核者",
    "检验者",
    "检验时间",
    "发布时",
    "入院记录",
    "入院诊断",
    "入院后计划",
    "既往史",
    "个人史",
    "婚育史",
    "家族史",
    "体格检查",
    "辅助检查",
    "濮撳悕",
    "鐥呭巻鍙",
    "鐥呮鍙",
    "鎬у埆",
    "骞撮緞",
    "绉戝埆",
    "涓村簥璇婃柇",
    "閲囨牱鏃堕棿",
    "鎺ユ敹鏃堕棿",
    "鎶ュ憡鏃堕棿",
    "鍦板潃",
    "鐢佃瘽",
    "涓嬭浇",
    "鍑洪櫌",
    "鐥呮儏鎽樿",
    "娌荤枟寤鸿",
    "鍖诲笀绛惧瓧",
    "鏃ユ湡",
    "瀹℃牳鑰",
    "妫€楠岃€",
    "妫€楠屾椂闂",
    "鍙戝竷鏃堕棿",
    "互认项目",
    "停用字",
    "项目标志",
)
_VALUE_RE = re.compile(r"[<>]?\d+(?:\.\d+)?")
_REFERENCE_RE = re.compile(r"^(?:[<>]?\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?)$")
_UNIT_RE = re.compile(
    r"^(?:10\^\d+/L|g/L|g/dL|mg/dL|mmol/L|umol/L|[\u03bc\u00b5]mol/L|ng/ml|ng/mL|U/L|IU/L|fL|fl|pg|%|tp/ml)$",
    re.IGNORECASE,
)
_EMBEDDED_TABLE_DATA_RE = re.compile(
    r"([鈽呪槅*★☆]?[^\s]{0,24}(?:WBC|RBC|HGB|PLT|TP|ALB|AST|ALT|cTnT|CTNT)[^\s)]*\)?\s+[<>]?\d.*)$"
)
_NARRATIVE_FACT_PATTERNS: tuple[tuple[str, str, re.Pattern[str], dict[str, str]], ...] = (
    (
        "stage_admission",
        "time_phase",
        re.compile(r"\badmission note\b|\badmission record\b|入院记录|收住入院|入院", re.IGNORECASE),
        {"phase": "admission"},
    ),
    (
        "stage_discharge",
        "time_phase",
        re.compile(r"\bdischarge note\b|出院", re.IGNORECASE),
        {"phase": "discharge"},
    ),
    (
        "complaint_reported",
        "complaint",
        re.compile(r"\b(?:the patient )?reports\b|\bcomplains of\b", re.IGNORECASE),
        {"label": "reported_complaint"},
    ),
    (
        "symptom_dizziness",
        "observation",
        re.compile(r"\bdizziness\b|头晕|眩晕", re.IGNORECASE),
        {"label": "dizziness"},
    ),
    (
        "symptom_fatigue",
        "observation",
        re.compile(r"\bfatigue\b|乏力|疲乏", re.IGNORECASE),
        {"label": "fatigue"},
    ),
    (
        "symptom_cough",
        "observation",
        re.compile(r"\bcough\b|咳嗽", re.IGNORECASE),
        {"label": "cough"},
    ),
    (
        "symptom_chest_tightness",
        "observation",
        re.compile(r"\bchest tightness\b|胸闷", re.IGNORECASE),
        {"label": "chest_tightness"},
    ),
    (
        "symptom_edema",
        "observation",
        re.compile(r"\bedema\b|水肿", re.IGNORECASE),
        {"label": "edema"},
    ),
    (
        "symptom_abdominal_distension",
        "observation",
        re.compile(r"\babdominal distension\b|\bbloating\b|腹胀", re.IGNORECASE),
        {"label": "abdominal_distension"},
    ),
    (
        "symptom_shortness_of_breath",
        "observation",
        re.compile(r"\bshortness of breath\b|\bdyspnea\b|气促|呼吸困难", re.IGNORECASE),
        {"label": "shortness_of_breath"},
    ),
    (
        "followup_glucose",
        "recommendation",
        re.compile(
            r"(follow[- ]?up|monitor(?:ing)?|复查|监测).{0,16}(glucose|blood sugar|血糖)|(glucose|blood sugar|血糖).{0,16}(follow[- ]?up|monitor(?:ing)?|复查|监测)",
            re.IGNORECASE,
        ),
        {"action": "follow_up", "target": "glucose"},
    ),
    (
        "repeat_blood_count",
        "recommendation",
        re.compile(
            r"(repeat|follow[- ]?up|复查).{0,16}(blood count|cbc|血常规)|(blood count|cbc|血常规).{0,16}(repeat|follow[- ]?up|复查)",
            re.IGNORECASE,
        ),
        {"action": "repeat_test", "target": "blood_count"},
    ),
    (
        "continue_observation",
        "recommendation",
        re.compile(r"\bcontinue observation\b|继续观察", re.IGNORECASE),
        {"action": "continue_observation"},
    ),
    (
        "outpatient_followup",
        "recommendation",
        re.compile(r"\boutpatient follow[- ]?up\b|\bclinic review\b|\bclinic follow[- ]?up\b|门诊随访", re.IGNORECASE),
        {"action": "outpatient_follow_up"},
    ),
    (
        "status_no_structured_lab_table",
        "status",
        re.compile(
            r"\bno (?:structured|explicit) lab table was preserved\b|\bno structured lab table\b|\bno explicit lab table\b",
            re.IGNORECASE,
        ),
        {"label": "no_structured_lab_table_preserved", "polarity": "negative", "target": "structured_lab_table"},
    ),
)


def extract_legacy_measurements(raw_text: str) -> list[dict]:
    measurements: list[dict] = []
    for line in raw_text.splitlines():
        normalized_line = line.strip()
        if not normalized_line or "=" not in normalized_line:
            continue
        measurement = _parse_equals_line(normalized_line)
        if measurement is not None:
            measurements.append(measurement)
    return measurements


class RuleBasedNormalizationProvider(NormalizationProvider):
    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config or ProviderConfig(provider_type="normalization", name="rule_based"))

    def normalize(self, raw_text: str) -> NormalizationResult:
        legacy_measurements = extract_legacy_measurements(raw_text)
        extracted_measurements = self._extract_measurements(raw_text)
        prose_facts = _extract_prose_facts(raw_text)
        document_category = infer_document_category(
            raw_text=raw_text,
            measurements=extracted_measurements,
            document_type="generic_record",
        )
        report_date = extract_report_date(raw_text)
        measurements = extracted_measurements if document_category == STRUCTURED_METRICS else []
        document_type = "lab_report" if document_category == STRUCTURED_METRICS else "clinical_note"
        capabilities = category_capabilities(document_category)

        return NormalizationResult(
            provider_name=self.config.name,
            document_type=document_type,
            document_category=document_category,
            report_date=report_date,
            supports_measurements=capabilities["supports_measurements"],
            supports_trend_analysis=capabilities["supports_trend_analysis"],
            supports_llm_context=capabilities["supports_llm_context"],
            normalized_payload={
                "raw_text": raw_text,
                "report_date": report_date.isoformat() if report_date else None,
                "document_category": document_category,
                "measurement_count": len(measurements),
                "candidate_measurement_count": len(extracted_measurements),
                "legacy_measurement_count": len(legacy_measurements),
                "prose_fact_count": len(prose_facts),
                "prose_facts": prose_facts,
                "measurements": measurements,
                "canonicalization_notes": [
                    {
                        "source_name": item["source_name"],
                        "canonical_name": item["name"],
                        "cleaned_name_token": item["cleaned_name_token"],
                    }
                    for item in extracted_measurements
                    if item["canonicalization_applied"]
                ],
                "table_parser_notes": [
                    {
                        "source_row": item["source_row"],
                        "name": item["name"],
                        "source_name": item["source_name"],
                        "reference_range": item.get("reference_range"),
                        "parser": item["parser"],
                        "partial": item["value_numeric"] is None or item["unit"] is None,
                    }
                    for item in extracted_measurements
                    if item["parser"] != "legacy_equals"
                ],
                "prose_parser_notes": [
                    {
                        "fact_id": fact["fact_id"],
                        "fact_type": fact["fact_type"],
                        "parser": fact["parser"],
                        "matched_text": fact["matched_text"],
                    }
                    for fact in prose_facts
                ],
            },
            measurements=measurements,
        )

    def _extract_measurements(self, raw_text: str) -> list[dict]:
        measurements: list[dict] = []
        seen_rows: set[tuple[str, str, str | None]] = set()

        for item in extract_legacy_measurements(raw_text):
            dedupe_key = (item["name"], item["value_text"], item.get("unit"))
            if dedupe_key in seen_rows:
                continue
            seen_rows.add(dedupe_key)
            measurements.append(item)

        for line in _merge_table_fragments(raw_text.splitlines()):
            if "=" in line:
                continue
            measurement = self._parse_table_line(line)
            if measurement is None:
                continue
            dedupe_key = (measurement["name"], measurement["value_text"], measurement.get("unit"))
            if dedupe_key in seen_rows:
                continue
            seen_rows.add(dedupe_key)
            measurements.append(measurement)
        return measurements

    def _parse_table_line(self, raw_line: str) -> dict | None:
        normalized_line = _normalize_table_line(raw_line)
        if not normalized_line or _should_skip_table_line(normalized_line):
            return None

        row_body = re.sub(r"^\d+\s+", "", normalized_line).strip()
        has_leading_index = bool(re.match(r"^\d+\s+", normalized_line))
        value_match = _VALUE_RE.search(row_body)
        if value_match is None or value_match.start() == 0:
            return None

        name_segment = row_body[: value_match.start()].strip()
        if not _looks_like_metric_name(name_segment):
            return None

        canonical_name = canonicalize_metric_name(name_segment)
        value_token = value_match.group(0)
        value_numeric = self._try_parse_float(value_token)
        if value_numeric is None and value_token[:1] in {"<", ">"}:
            value_numeric = self._try_parse_float(value_token[1:])
        if value_numeric is None:
            return None

        tail = row_body[value_match.end() :].strip()
        unit, reference_range = _extract_unit_and_reference(tail)
        if not _is_supported_table_metric(
            name_segment=name_segment,
            canonical_changed=canonical_name.changed,
            unit=unit,
            reference_range=reference_range,
            has_leading_index=has_leading_index,
        ):
            return None
        return {
            "name": canonical_name.canonical_name,
            "source_name": canonical_name.source_name,
            "cleaned_name_token": canonical_name.cleaned_token,
            "canonicalization_applied": canonical_name.changed,
            "value_text": f"{value_token} {unit}".strip() if unit is not None else value_token,
            "value_numeric": value_numeric,
            "unit": unit,
            "reference_range": reference_range,
            "source_row": normalized_line,
            "parser": "table_row",
        }

    def _try_parse_float(self, raw_value: str) -> float | None:
        try:
            return float(raw_value)
        except ValueError:
            return None


def _parse_equals_line(normalized_line: str) -> dict | None:
    name, raw_value = normalized_line.split("=", maxsplit=1)
    canonical_name = canonicalize_metric_name(name)
    parsed_value = raw_value.strip()
    value_numeric = _try_parse_float(parsed_value)
    unit = None
    if value_numeric is None:
        value_part, _, unit_part = parsed_value.partition(" ")
        value_numeric = _try_parse_float(value_part)
        if value_numeric is None and value_part[:1] in {"<", ">"}:
            value_numeric = _try_parse_float(value_part[1:])
        if value_numeric is not None:
            unit = unit_part.strip() or None
    return {
        "name": canonical_name.canonical_name,
        "source_name": canonical_name.source_name,
        "cleaned_name_token": canonical_name.cleaned_token,
        "canonicalization_applied": canonical_name.changed,
        "value_text": parsed_value,
        "value_numeric": value_numeric,
        "unit": unit,
        "reference_range": None,
        "source_row": normalized_line,
        "parser": "legacy_equals",
    }


def _normalize_table_line(raw_line: str) -> str:
    line = raw_line.replace("\t", " ")
    line = line.replace("／", "/")
    line = line.replace("×", "^")
    line = line.replace("µ", "u").replace("μ", "u")
    line = re.sub(r"\)\s*(?=[<>]?\d)", ") ", line)
    line = re.sub(r"(?<=[A-Za-z])\s*/\s*(?=[A-Za-z])", "/", line)
    line = re.sub(r"\s+", " ", line)
    line = line.strip()
    return _strip_embedded_header_prefix(line)


def _strip_embedded_header_prefix(line: str) -> str:
    match = _EMBEDDED_TABLE_DATA_RE.search(line)
    if match is None:
        return line
    prefix = line[: match.start(1)]
    if any(marker in prefix for marker in _TABLE_HEADER_MARKERS):
        return match.group(1).strip()
    return line


def _merge_table_fragments(lines: list[str]) -> list[str]:
    merged_lines: list[str] = []
    index = 0
    while index < len(lines):
        current = _normalize_table_line(lines[index])
        if (
            current
            and index + 1 < len(lines)
            and not _should_skip_table_line(current)
            and _looks_like_metric_fragment(current)
            and _starts_with_value_fragment(lines[index + 1])
        ):
            current = f"{current} {_normalize_table_line(lines[index + 1])}"
            index += 1
        if current:
            merged_lines.append(current)
        index += 1
    return merged_lines


def _should_skip_table_line(line: str) -> bool:
    if any(marker in line for marker in _TABLE_HEADER_MARKERS):
        return True
    if any(marker in line for marker in _NON_DATA_MARKERS):
        return True
    if "锛" in line and not any(token in line for token in ("(", ")", "WBC", "HGB", "PLT", "TP", "ALB", "AST", "ALT", "cTnT")):
        return True
    return False


def _looks_like_metric_fragment(line: str) -> bool:
    candidate = re.sub(r"^\d+\s+", "", line).strip()
    if not candidate or "=" in candidate:
        return False
    if _should_skip_table_line(candidate):
        return False
    if _VALUE_RE.search(candidate):
        return False
    return _looks_like_metric_name(candidate)


def _starts_with_value_fragment(line: str) -> bool:
    return _VALUE_RE.match(_normalize_table_line(line)) is not None


def _looks_like_metric_name(name_segment: str) -> bool:
    cleaned_name = name_segment.lstrip("鈽呪槅*★☆ ").strip()
    if not cleaned_name or len(cleaned_name) > 120:
        return False
    if cleaned_name.isdigit():
        return False
    if all(marker not in cleaned_name for marker in ("(", ")", "WBC", "RBC", "HGB", "PLT", "TP", "ALB", "AST", "ALT", "cTnT", "CTNT")):
        has_chinese = any("\u4e00" <= char <= "\u9fff" for char in cleaned_name)
        has_ascii = any(char.isalpha() for char in cleaned_name)
        if not has_chinese and not has_ascii:
            return False
    return True


def _extract_unit_and_reference(raw_tail: str) -> tuple[str | None, str | None]:
    if not raw_tail:
        return None, None

    tokens = [token.strip("，。,;；:：") for token in raw_tail.split(" ") if token.strip("，。,;；:：")]
    unit = None
    reference_range = None
    for token in tokens:
        normalized_token = _normalize_unit_token(token)
        if unit is None and _UNIT_RE.match(normalized_token):
            unit = normalized_token
            continue
        if reference_range is None and _REFERENCE_RE.match(token):
            reference_range = token
    return unit, reference_range


def _normalize_unit_token(token: str) -> str:
    normalized = token.replace("\uFF0F", "/").replace("\u03BC", "u").replace("\u00B5", "u")
    if normalized.lower() == "iu/l":
        return "U/L"
    return normalized


def _is_supported_table_metric(
    *,
    name_segment: str,
    canonical_changed: bool,
    unit: str | None,
    reference_range: str | None,
    has_leading_index: bool,
) -> bool:
    if canonical_changed:
        return True
    if "(" in name_segment and ")" in name_segment:
        return True
    return has_leading_index and unit is not None and reference_range is not None


def _try_parse_float(raw_value: str) -> float | None:
    try:
        return float(raw_value)
    except ValueError:
        return None


def _extract_prose_facts(raw_text: str) -> list[dict]:
    facts: list[dict] = []
    seen_fact_ids: set[str] = set()
    lines = [_normalize_narrative_line(line) for line in raw_text.splitlines()]

    for line in lines:
        if not line or "=" in line:
            continue
        for fact_id, fact_type, pattern, attributes in _NARRATIVE_FACT_PATTERNS:
            match = pattern.search(line)
            if match is None or fact_id in seen_fact_ids:
                continue
            seen_fact_ids.add(fact_id)
            fact = {
                "fact_id": fact_id,
                "fact_type": fact_type,
                "parser": "narrative_prose",
                "source_line": line,
                "matched_text": match.group(0).strip(),
                "attributes": dict(attributes),
            }
            if fact_type == "observation":
                fact["display_text"] = f"Observed {attributes['label']}"
            elif fact_type == "time_phase":
                fact["display_text"] = f"Phase: {attributes['phase']}"
            elif fact_type in {"complaint", "status"}:
                fact["display_text"] = attributes["label"]
            else:
                action = attributes.get("action", "noted")
                target = attributes.get("target")
                fact["display_text"] = f"{action}:{target}" if target else action
            facts.append(fact)
    return facts


def _normalize_narrative_line(raw_line: str) -> str:
    line = raw_line.replace("\t", " ")
    line = re.sub(r"\s+", " ", line)
    return line.strip(" .;:,-")
