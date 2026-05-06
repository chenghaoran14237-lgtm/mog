from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(slots=True, frozen=True)
class CanonicalMetricName:
    source_name: str
    canonical_name: str
    cleaned_token: str

    @property
    def changed(self) -> bool:
        return self.source_name != self.canonical_name


_ALIAS_MAP = {
    "glucose": "glucose",
    "glu": "glucose",
    "gluc": "glucose",
    "葡萄糖": "glucose",
    "血糖": "glucose",
    "hemoglobin": "hemoglobin",
    "hgb": "hemoglobin",
    "hb": "hemoglobin",
    "血红蛋白": "hemoglobin",
    "血红蛋白浓度": "hemoglobin",
    "platelet": "platelet",
    "platelets": "platelet",
    "plt": "platelet",
    "血小板": "platelet",
    "血小板计数": "platelet",
    "wbc": "wbc",
    "白细胞计数": "wbc",
    "白细胞数": "wbc",
    "rbc": "rbc",
    "红细胞计数": "rbc",
    "红细胞": "rbc",
    "hct": "hematocrit",
    "红细胞比积": "hematocrit",
    "红细胞压积": "hematocrit",
    "mcv": "mcv",
    "平均红细胞体积": "mcv",
    "mch": "mch",
    "平均红细胞血红蛋白量": "mch",
    "平均红色血红蛋白含量": "mch",
    "mchc": "mchc",
    "平均rbc血红蛋白浓度": "mchc",
    "平均红细胞血红蛋白浓度": "mchc",
    "平均血小板体积": "mpv",
    "mpv": "mpv",
    "pdw": "pdw",
    "血小板体积分布宽度": "pdw",
    "血小板分布宽度": "pdw",
    "pct": "pct",
    "血小板压积": "pct",
    "tp": "total_protein",
    "总蛋白": "total_protein",
    "alb": "albumin",
    "白蛋白": "albumin",
    "ag": "albumin_globulin_ratio",
    "白球比": "albumin_globulin_ratio",
    "ast": "ast",
    "谷草转氨酶": "ast",
    "alt": "alt",
    "谷丙转氨酶": "alt",
    "alp": "alp",
    "碱性磷酸酶": "alp",
    "ggt": "ggt",
    "谷氨酰转肽酶": "ggt",
    "γ谷氨酰转肽酶": "ggt",
    "tbil": "total_bilirubin",
    "总胆红素": "total_bilirubin",
    "dbil": "direct_bilirubin",
    "直接胆红素": "direct_bilirubin",
    "ibil": "indirect_bilirubin",
    "间接胆红素": "indirect_bilirubin",
    "tba": "total_bile_acid",
    "总胆汁酸": "total_bile_acid",
    "idbil": "indirect_bilirubin",
    "che": "cholinesterase",
    "pche": "cholinesterase",
    "ldh": "ldh",
    "crea": "creatinine",
    "egfr": "egfr",
    "ua": "uric_acid",
    "na": "sodium",
    "k": "potassium",
    "ctnt": "ctnt",
    "troponint": "ctnt",
}


def canonicalize_metric_name(raw_name: str) -> CanonicalMetricName:
    source_name = " ".join(raw_name.strip().split())
    tokens = _candidate_tokens(source_name)
    cleaned_token = _clean_token(source_name)
    canonical_name = source_name
    for token in tokens:
        mapped_name = _ALIAS_MAP.get(token)
        if mapped_name is not None:
            canonical_name = mapped_name
            break
    return CanonicalMetricName(
        source_name=source_name,
        canonical_name=canonical_name,
        cleaned_token=cleaned_token,
    )


def _candidate_tokens(source_name: str) -> list[str]:
    normalized_name = source_name.lstrip("★☆* ").strip()
    candidates: list[str] = []
    for match in re.finditer(r"\(([^)]+)\)", normalized_name):
        candidates.append(_clean_token(match.group(1)))
    for match in re.finditer(r"[A-Za-z][A-Za-z0-9/%#^.-]*", normalized_name):
        candidates.append(_clean_token(match.group(0)))
    candidates.append(_clean_token(normalized_name))
    candidates.append(_clean_token(re.sub(r"\([^)]*\)", "", normalized_name)))

    ordered_candidates: list[str] = []
    seen_tokens: set[str] = set()
    for token in candidates:
        if not token or token in seen_tokens:
            continue
        seen_tokens.add(token)
        ordered_candidates.append(token)
    return ordered_candidates


def _clean_token(raw_token: str) -> str:
    return "".join(char.lower() for char in raw_token if char.isalnum())
