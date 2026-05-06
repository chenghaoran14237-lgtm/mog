from __future__ import annotations

import re
from datetime import datetime

from app.models.document_version import DocumentVersion
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.measurement_repository import MeasurementRepository


class ConversationContextService:
    """对话上下文构建服务"""

    _MAX_RAW_TEXT_CHARS = 2600
    _MAX_MEASUREMENTS_PER_DOC = 20
    _MAX_PROSE_FACTS_PER_DOC = 12

    def __init__(
        self,
        document_version_repo: DocumentVersionRepository,
        measurement_repo: MeasurementRepository,
    ) -> None:
        self.document_version_repo = document_version_repo
        self.measurement_repo = measurement_repo

    def build_context(
        self,
        *,
        user_id: int,
        selected_document_ids: list[int],
        selected_measurement_names: list[str] | None = None,
    ) -> str:
        """按文档 ID 构建上下文"""
        versions: list[DocumentVersion] = []
        for document_id in selected_document_ids:
            version = self.document_version_repo.get_current_for_document(document_id, user_id=user_id)
            if version is not None:
                versions.append(version)
        return self._build_context_from_versions(
            versions=versions,
            selected_measurement_names=selected_measurement_names,
        )

    def build_context_for_version_ids(
        self,
        *,
        user_id: int,
        selected_version_ids: list[int],
        selected_measurement_names: list[str] | None = None,
    ) -> str:
        """按版本 ID 构建上下文，用于批量分析"""
        versions: list[DocumentVersion] = []
        for version_id in selected_version_ids:
            version = self.document_version_repo.get_by_id(version_id, user_id=user_id)
            if version is not None:
                versions.append(version)
        return self._build_context_from_versions(
            versions=versions,
            selected_measurement_names=selected_measurement_names,
        )

    def _build_context_from_versions(
        self,
        *,
        versions: list[DocumentVersion],
        selected_measurement_names: list[str] | None = None,
    ) -> str:
        if not versions:
            return ""

        structured_count = 0
        narrative_count = 0
        total_measurements = 0
        context_parts = [
            "你正在阅读用户选中的健康档案。请像谨慎的私人家庭医生一样，综合不同报告中的检查结果、病历叙述、诊断、治疗经过、出院医嘱和时间顺序来回答。",
            "不要把分析局限在数值指标上。即使某份文档没有结构化测量值，只要有病历正文，也必须纳入临床分析。",
            "回答时优先给出：整体判断、关键信号、可能风险、复查与就医建议、需要继续观察的事项。不要声称自己没有看到报告，除非上下文里确实为空。",
        ]

        for index, version in enumerate(versions, start=1):
            document = version.document
            payload = version.normalized_payload or {}
            category = str(
                payload.get("document_category")
                or getattr(document, "document_category", "")
                or "unknown"
            )
            report_date = version.report_date or getattr(document, "report_date", None) or version.created_at
            raw_text = self._normalize_raw_text(str(payload.get("raw_text") or ""))
            prose_facts = payload.get("prose_facts") or []
            measurements = list(version.measurements or [])

            if category == "structured_metrics":
                structured_count += 1
            else:
                narrative_count += 1
            total_measurements += len(measurements)

            title = (
                getattr(document, "display_name", None)
                or f"文档 {getattr(document, 'id', version.document_id)}"
            )

            context_parts.append("")
            context_parts.append(f"=== 文档 {index} ===")
            context_parts.append(f"标题：{title}")
            context_parts.append(f"文档类别：{self._category_label(category)}")
            context_parts.append(f"报告日期：{self._format_datetime(report_date)}")
            context_parts.append(f"版本号：{version.version_number}")

            if measurements:
                measurement_lines = self._render_measurements(
                    measurements=measurements,
                    selected_measurement_names=selected_measurement_names,
                )
                if measurement_lines:
                    context_parts.append("结构化指标：")
                    context_parts.extend(measurement_lines)

            if prose_facts:
                context_parts.append("病历要点：")
                for fact in prose_facts[: self._MAX_PROSE_FACTS_PER_DOC]:
                    display_text = str(fact.get("display_text") or fact.get("matched_text") or "").strip()
                    if display_text:
                        context_parts.append(f"- {display_text}")

            if raw_text:
                context_parts.append("报告正文：")
                context_parts.append(self._clip_text(raw_text, self._MAX_RAW_TEXT_CHARS))

        summary = (
            f"共选中 {len(versions)} 份文档，其中结构化指标报告 {structured_count} 份，"
            f"病历叙事文档 {narrative_count} 份，累计结构化测量 {total_measurements} 条。"
        )

        return summary + "\n\n" + "\n".join(context_parts)

    def _render_measurements(
        self,
        *,
        measurements: list,
        selected_measurement_names: list[str] | None,
    ) -> list[str]:
        lines: list[str] = []
        for measurement in measurements[: self._MAX_MEASUREMENTS_PER_DOC]:
            if selected_measurement_names and measurement.name not in selected_measurement_names:
                continue
            observed_at = self._format_datetime(measurement.observed_at)
            unit = f" {measurement.unit}" if measurement.unit else ""
            numeric = (
                f"{measurement.value_numeric:g}{unit}"
                if measurement.value_numeric is not None
                else measurement.value_text
            )
            if observed_at != "--":
                lines.append(f"- {measurement.name}: {numeric}（时间：{observed_at}）")
            else:
                lines.append(f"- {measurement.name}: {numeric}")
        return lines

    def _normalize_raw_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _clip_text(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "\n\n[后续正文已截断]"

    def _format_datetime(self, value: datetime | None) -> str:
        if value is None:
            return "--"
        return value.strftime("%Y-%m-%d %H:%M")

    def _category_label(self, value: str) -> str:
        if value == "structured_metrics":
            return "结构化指标报告"
        if value == "narrative_context":
            return "病历叙事文档"
        return value or "--"
