from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.router import api_router
from app.core.config import get_settings
from app.core.db import Base
from app.models import (  # noqa: F401 - import registers models in Base.metadata
    AuditReportEvent,
    AuditReportNodeState,
    AuditReportRun,
    DocumentVersion,
    ExtractedDocument,
    Measurement,
    OCRResult,
    ProviderEvent,
    Record,
    RecordFile,
    Task,
    TaskEvent,
    User,
)
from app.services.audit_graph.engine import AUDIT_GRAPH_EDGES
from scripts.seed_mock_exam_data import MOCK_DOCUMENTS


OUT_DIR = ROOT / "docs" / "thesis_assets" / "figures"
SNAPSHOT_FILE = ROOT / "docs" / "thesis_assets" / "project_snapshot.json"

PALETTE = {
    "ink": "#1f2933",
    "muted": "#64748b",
    "line": "#b7c3cc",
    "soft": "#f5f8fa",
    "panel": "#ffffff",
    "blue": "#2f6f9f",
    "blue_soft": "#dcebf5",
    "green": "#2f7d57",
    "green_soft": "#dff1e7",
    "orange": "#b06b2b",
    "orange_soft": "#f6e8d8",
    "red": "#a94949",
    "red_soft": "#f2dfdf",
    "purple": "#6f5f9e",
    "purple_soft": "#e9e5f4",
    "gray_soft": "#eef2f5",
}


def _font_path(*names: str) -> str:
    candidates = [
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/Deng.ttf"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    candidates.extend(Path("C:/Windows/Fonts") / name for name in names)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


FONT_REGULAR = _font_path()
FONT_BOLD = _font_path("msyhbd.ttc", "Dengb.ttf", "NotoSans-Bold.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = FONT_BOLD if bold and FONT_BOLD else FONT_REGULAR
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def blend(color: str, alpha: float, bg: str = "#ffffff") -> tuple[int, int, int]:
    c = hex_to_rgb(color)
    b = hex_to_rgb(bg)
    return tuple(int(c[i] * alpha + b[i] * (1 - alpha)) for i in range(3))


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, width: int) -> list[str]:
    if not text:
        return [""]
    chunks: list[str] = []
    current = ""
    for char in text:
        trial = current + char
        if text_size(draw, trial, fnt)[0] <= width or not current:
            current = trial
        else:
            chunks.append(current)
            current = char
    if current:
        chunks.append(current)
    return chunks


class Canvas:
    def __init__(self, width: int, height: int, title: str, subtitle: str | None = None) -> None:
        self.image = Image.new("RGB", (width, height), PALETTE["soft"])
        self.draw = ImageDraw.Draw(self.image)
        self.width = width
        self.height = height
        self.margin = 48
        self.draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=28, fill="#ffffff", outline="#d8e1e8", width=2)
        self.draw.text((self.margin, 38), title, fill=PALETTE["ink"], font=font(34, True))
        if subtitle:
            self.draw.text((self.margin, 82), subtitle, fill=PALETTE["muted"], font=font(20))
        self.draw.line((self.margin, 122, width - self.margin, 122), fill=PALETTE["line"], width=2)

    def panel(self, xy: tuple[int, int, int, int], title: str | None = None, fill: str = "#ffffff") -> None:
        self.draw.rounded_rectangle(xy, radius=20, fill=fill, outline="#d3dde5", width=2)
        if title:
            self.draw.text((xy[0] + 20, xy[1] + 14), title, fill=PALETTE["ink"], font=font(22, True))

    def box(
        self,
        xy: tuple[int, int, int, int],
        title: str,
        body: str | Iterable[str] = "",
        *,
        fill: str = "#ffffff",
        stroke: str = "#b7c3cc",
        accent: str = "#2f6f9f",
        title_size: int = 22,
        body_size: int = 16,
    ) -> None:
        x1, y1, x2, y2 = xy
        self.draw.rounded_rectangle(xy, radius=18, fill=fill, outline=stroke, width=2)
        self.draw.rounded_rectangle((x1, y1, x1 + 10, y2), radius=8, fill=accent)
        self.draw.text((x1 + 22, y1 + 15), title, fill=PALETTE["ink"], font=font(title_size, True))
        body_lines = list(body) if not isinstance(body, str) else wrap_text(self.draw, body, font(body_size), x2 - x1 - 44)
        y = y1 + 48
        for line in body_lines[: max(1, (y2 - y - 8) // (body_size + 8))]:
            self.draw.text((x1 + 22, y), line, fill=PALETTE["muted"], font=font(body_size))
            y += body_size + 8

    def arrow(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        *,
        color: str = "#64748b",
        width: int = 3,
        label: str | None = None,
        elbow: tuple[int, int] | None = None,
    ) -> None:
        points = [start]
        if elbow:
            points.append(elbow)
        points.append(end)
        self.draw.line(points, fill=color, width=width, joint="curve")
        self._arrow_head(points[-2], points[-1], color=color, size=12 + width)
        if label:
            mx = sum(p[0] for p in points) // len(points)
            my = sum(p[1] for p in points) // len(points)
            tw, th = text_size(self.draw, label, font(15, True))
            self.draw.rounded_rectangle((mx - tw // 2 - 8, my - th // 2 - 6, mx + tw // 2 + 8, my + th // 2 + 6), radius=8, fill="#ffffff", outline="#dae2e8")
            self.draw.text((mx - tw // 2, my - th // 2), label, fill=color, font=font(15, True))

    def poly_arrow(
        self,
        points: list[tuple[int, int]],
        *,
        color: str = "#64748b",
        width: int = 3,
        label: str | None = None,
    ) -> None:
        self.draw.line(points, fill=color, width=width, joint="curve")
        self._arrow_head(points[-2], points[-1], color=color, size=12 + width)
        if label:
            mid = points[len(points) // 2]
            tw, th = text_size(self.draw, label, font(15, True))
            self.draw.rounded_rectangle((mid[0] - tw // 2 - 8, mid[1] - th // 2 - 6, mid[0] + tw // 2 + 8, mid[1] + th // 2 + 6), radius=8, fill="#ffffff", outline="#dae2e8")
            self.draw.text((mid[0] - tw // 2, mid[1] - th // 2), label, fill=color, font=font(15, True))

    def _arrow_head(self, start: tuple[int, int], end: tuple[int, int], *, color: str, size: int) -> None:
        sx, sy = start
        ex, ey = end
        angle = math.atan2(ey - sy, ex - sx)
        p1 = (ex - size * math.cos(angle - math.pi / 6), ey - size * math.sin(angle - math.pi / 6))
        p2 = (ex - size * math.cos(angle + math.pi / 6), ey - size * math.sin(angle + math.pi / 6))
        self.draw.polygon([end, p1, p2], fill=color)

    def save(self, name: str) -> Path:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / name
        self.image.save(path, quality=96)
        return path


def route_groups() -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for route in api_router.routes:
        path = getattr(route, "path", "")
        methods = sorted(getattr(route, "methods", []) or [])
        if not path or not methods:
            continue
        first = path.strip("/").split("/", maxsplit=1)[0] or "root"
        groups[first].append(f"{','.join(methods)} {path}")
    return dict(groups)


def mock_summary() -> dict:
    doc_counter = Counter(spec.document_category for spec in MOCK_DOCUMENTS)
    type_counter = Counter(spec.document_type for spec in MOCK_DOCUMENTS)
    measurement_total = sum(len(spec.measurements) for spec in MOCK_DOCUMENTS)
    prose_total = sum(len(spec.prose_facts) for spec in MOCK_DOCUMENTS)
    monthly = Counter(spec.report_date[:7] for spec in MOCK_DOCUMENTS)
    return {
        "document_count": len(MOCK_DOCUMENTS),
        "measurement_count": measurement_total,
        "prose_fact_count": prose_total,
        "document_categories": dict(doc_counter),
        "document_types": dict(type_counter),
        "monthly_documents": dict(sorted(monthly.items())),
    }


def draw_scenario() -> Path:
    c = Canvas(1600, 900, "医疗审计场景与系统边界", "真实项目围绕个人健康资料整理、结构化入库和非诊断性审计提示展开")
    c.box((70, 190, 330, 310), "用户资料", ["体检报告", "检验单", "病历摘要", "随访记录"], fill=PALETTE["blue_soft"], accent=PALETTE["blue"])
    c.box((70, 380, 330, 500), "系统处理", ["上传", "OCR", "标准化", "版本追踪"], fill=PALETTE["green_soft"], accent=PALETTE["green"])
    c.box((70, 570, 330, 690), "输出边界", ["健康信息整理", "风险提示", "来源追溯", "不替代诊断"], fill=PALETTE["orange_soft"], accent=PALETTE["orange"])
    c.box((500, 180, 760, 300), "数据资产层", ["record_files", "ocr_results", "document_versions", "measurements"], accent=PALETTE["blue"])
    c.box((500, 390, 760, 510), "多 Agent 审计层", ["质量审计", "指标一致性", "冲突复核", "安全审查"], accent=PALETTE["purple"])
    c.box((500, 600, 760, 720), "前端工作台", ["文档库", "指标探索", "智能洞察", "综合审计报告"], accent=PALETTE["green"])
    c.box((970, 230, 1300, 350), "论文核心问题", "如何让医疗资料从原文、结构化指标到审计结论保持可追溯。", fill="#ffffff", accent=PALETTE["red"])
    c.box((970, 500, 1300, 620), "技术落点", "使用 LangGraph 将审计过程组织为可回环、可记录、可复核的状态机。", fill="#ffffff", accent=PALETTE["purple"])
    c.arrow((330, 250), (500, 240), label="接入")
    c.arrow((330, 440), (500, 450), label="入库")
    c.arrow((760, 450), (970, 290), label="审计依据")
    c.arrow((760, 650), (970, 560), label="可视化")
    c.arrow((635, 300), (635, 390), color=PALETTE["purple"], label="状态流转")
    c.arrow((635, 510), (635, 600), color=PALETTE["green"], label="展示")
    return c.save("图1-1_医疗审计场景与系统边界.png")


def draw_provider_architecture() -> Path:
    settings = get_settings()
    c = Canvas(1600, 940, "Provider 抽象与外部能力接入", "配置来自 .env，业务层只依赖统一 Provider 接口")
    c.box((90, 200, 400, 330), "业务服务", ["OCRService", "NormalizationService", "ConversationService", "AuditReportService"], fill=PALETTE["blue_soft"], accent=PALETTE["blue"])
    c.box((545, 170, 865, 360), "ProviderGateway", ["记录 provider_events", "统一异常映射", "统计耗时", "隐藏外部服务差异"], fill=PALETTE["gray_soft"], accent=PALETTE["muted"])
    providers = [
        ("OCRProvider", f"当前：{settings.ocr_provider}", "plaintext / baidu_ocr / openai_compatible_vision"),
        ("NormalizationProvider", f"当前：{settings.normalization_provider}", "rule_based / llm_direct"),
        ("LLMProvider", f"当前：{settings.llm_provider}", "stub / openai_compatible"),
        ("StorageProvider", f"当前：{settings.storage_provider}", "database_inline"),
    ]
    y = 145
    for title, current, variants in providers:
        c.box((1040, y, 1450, y + 120), title, [current, variants], fill="#ffffff", accent=PALETTE["green"])
        c.arrow((865, 260), (1040, y + 60), color=PALETTE["green"])
        y += 155
    c.box((90, 530, 400, 680), "数据库留痕", ["provider_events", "tasks", "task_events", "audit_report_events"], fill=PALETTE["orange_soft"], accent=PALETTE["orange"])
    c.box((545, 530, 865, 680), "工程收益", ["可替换", "可追踪", "可降级", "可测试"], fill=PALETTE["purple_soft"], accent=PALETTE["purple"])
    c.arrow((400, 265), (545, 265), label="调用")
    c.arrow((705, 360), (705, 530), color=PALETTE["orange"], label="事件写入")
    c.arrow((400, 605), (545, 605), color=PALETTE["purple"], label="支撑")
    return c.save("图2-1_Provider抽象与外部能力接入.png")


def draw_langgraph_principle() -> Path:
    c = Canvas(1600, 960, "LangGraph 状态机机制", "节点读取共享 GraphState，返回局部更新，条件边决定下一步走向")
    c.box((110, 210, 370, 340), "GraphState", ["documents", "measurements", "findings", "evidence_items", "report_draft"], fill=PALETTE["blue_soft"], accent=PALETTE["blue"])
    c.box((585, 175, 870, 290), "节点函数", ["读取 state", "执行审计逻辑", "返回状态增量"], fill=PALETTE["green_soft"], accent=PALETTE["green"])
    c.box((585, 395, 870, 510), "条件路由", ["audit_router", "final_router", "根据缺口选择节点"], fill=PALETTE["purple_soft"], accent=PALETTE["purple"])
    c.box((1080, 210, 1380, 340), "持久化结果", ["audit_report_runs", "audit_report_events", "audit_report_node_states"], fill=PALETTE["orange_soft"], accent=PALETTE["orange"])
    c.box((355, 645, 570, 755), "可回环", "证据不足或安全审查失败时返回前序节点。", accent=PALETTE["red"])
    c.box((705, 645, 920, 755), "可观测", "每条边、每个节点完成事件都写入数据库。", accent=PALETTE["orange"])
    c.box((1055, 645, 1270, 755), "可复核", "最终报告绑定结构化指标和原文证据。", accent=PALETTE["green"])
    c.arrow((370, 275), (585, 235), label="输入")
    c.arrow((870, 235), (1080, 275), label="事件")
    c.arrow((730, 290), (730, 395), color=PALETTE["purple"], label="状态更新")
    c.arrow((585, 455), (370, 275), color=PALETTE["purple"], elbow=(460, 455), label="回写")
    c.arrow((870, 455), (1080, 275), color=PALETTE["orange"], elbow=(980, 455), label="完成")
    c.arrow((462, 645), (730, 510), color=PALETTE["red"])
    c.arrow((812, 645), (730, 510), color=PALETTE["orange"])
    c.arrow((1162, 645), (1230, 340), color=PALETTE["green"])
    return c.save("图2-2_LangGraph状态机机制.png")


def draw_system_architecture() -> Path:
    c = Canvas(1800, 1080, "系统总体架构", "前端工作台、FastAPI 后端、Provider 能力层和 MySQL 数据层共同形成闭环")
    c.panel((80, 160, 1720, 300), "前端展示层", fill="#fbfdff")
    front = ["系统控制台", "文档接入", "文档库", "综合审计报告", "智能洞察", "指标探索"]
    for i, label in enumerate(front):
        x = 130 + i * 260
        c.box((x, 210, x + 210, 270), label, "", fill=PALETTE["blue_soft"], accent=PALETTE["blue"], title_size=18)
    c.panel((80, 360, 1720, 520), "API 接口层", fill="#fbfdff")
    apis = ["auth", "files", "ocr", "ingestion", "query", "audit-reports", "insight/chat", "tasks"]
    for i, label in enumerate(apis):
        x = 120 + i * 195
        c.box((x, 415, x + 150, 475), label, "", fill="#ffffff", accent=PALETTE["green"], title_size=17)
    c.panel((80, 580, 1120, 880), "业务服务层", fill="#fbfdff")
    services = [
        ("FileUploadService", "原始文件和元数据"),
        ("OCRService", "OCR 识别"),
        ("NormalizationService", "结构化入库"),
        ("QueryService", "文档与指标查询"),
        ("AuditReportService", "LangGraph 审计报告"),
        ("InsightService", "对话式洞察"),
    ]
    for idx, (label, body) in enumerate(services):
        row, col = divmod(idx, 3)
        x = 130 + col * 315
        y = 640 + row * 115
        c.box((x, y, x + 270, y + 85), label, body, fill=PALETTE["gray_soft"], accent=PALETTE["muted"], title_size=17, body_size=14)
    c.panel((1190, 580, 1720, 880), "能力与数据层", fill="#fbfdff")
    c.box((1240, 635, 1475, 720), "ProviderRegistry", "OCR / LLM / Storage / Normalization", fill=PALETTE["purple_soft"], accent=PALETTE["purple"], title_size=17)
    c.box((1240, 765, 1475, 850), "MySQL 数据库", "业务表、任务表、审计事件表", fill=PALETTE["orange_soft"], accent=PALETTE["orange"], title_size=17)
    c.arrow((900, 300), (900, 360), label="HTTP")
    c.arrow((900, 520), (900, 580), label="依赖注入")
    c.arrow((1120, 730), (1240, 678), color=PALETTE["purple"], label="外部能力")
    c.arrow((1120, 790), (1240, 808), color=PALETTE["orange"], label="持久化")
    return c.save("图3-1_系统总体架构.png")


def draw_business_flow() -> Path:
    c = Canvas(1800, 920, "医疗资料处理与审计业务流程", "流程覆盖上传、OCR、标准化、版本化、查询和综合审计报告")
    steps = [
        ("资料上传", "record_files"),
        ("OCR 识别", "ocr_results"),
        ("文本标准化", "normalized_payload"),
        ("版本化入库", "document_versions"),
        ("指标索引", "measurements"),
        ("多 Agent 审计", "audit_report_runs/events"),
        ("报告展示", "final_report"),
    ]
    x = 80
    y = 360
    for i, (title, body) in enumerate(steps):
        fill = [PALETTE["blue_soft"], PALETTE["green_soft"], PALETTE["orange_soft"], PALETTE["purple_soft"]][i % 4]
        accent = [PALETTE["blue"], PALETTE["green"], PALETTE["orange"], PALETTE["purple"]][i % 4]
        c.box((x, y, x + 210, y + 120), title, body, fill=fill, accent=accent, title_size=19, body_size=15)
        if i < len(steps) - 1:
            c.arrow((x + 210, y + 60), (x + 270, y + 60), label=str(i + 1))
        x += 255
    c.box((255, 170, 520, 270), "后台任务", ["tasks", "task_events", "retry"], fill="#ffffff", accent=PALETTE["muted"])
    c.box((810, 170, 1095, 270), "Provider 事件", ["provider_events", "耗时", "失败原因"], fill="#ffffff", accent=PALETTE["orange"])
    c.box((1360, 170, 1640, 270), "前端轮询", ["任务状态", "节点状态", "事件流转"], fill="#ffffff", accent=PALETTE["green"])
    c.arrow((390, 270), (390, 360), color=PALETTE["muted"], label="调度")
    c.arrow((952, 270), (952, 360), color=PALETTE["orange"], label="留痕")
    c.arrow((1500, 270), (1500, 360), color=PALETTE["green"], label="展示")
    return c.save("图3-2_医疗资料处理与审计业务流程.png")


def draw_backend_layers() -> Path:
    c = Canvas(1600, 1000, "后端分层结构", "源码目录 app/ 按 API、服务、Provider、仓储和模型分层")
    layers = [
        ("api/v1", "HTTP 路由与鉴权依赖", ["auth.py", "files.py", "ocr.py", "ingestion.py", "audit_reports.py"]),
        ("services", "业务流程编排", ["task_processor.py", "normalization_service.py", "audit_report_service.py"]),
        ("providers", "外部能力抽象", ["ocr", "normalization", "llm", "storage"]),
        ("repositories", "数据访问封装", ["record_repository.py", "document_version_repository.py", "audit_report_repository.py"]),
        ("models/schemas", "数据库模型与响应模型", ["User", "DocumentVersion", "AuditReportRun", "Task"]),
        ("core", "配置、数据库、错误、日志", ["config.py", "db.py", "schema.py", "observability.py"]),
    ]
    y = 165
    for idx, (title, subtitle, files) in enumerate(layers):
        fill = "#ffffff" if idx % 2 else PALETTE["gray_soft"]
        c.box((130, y, 1470, y + 105), title, [subtitle, " / ".join(files)], fill=fill, accent=[PALETTE["blue"], PALETTE["green"], PALETTE["purple"], PALETTE["orange"]][idx % 4], title_size=22, body_size=16)
        if idx < len(layers) - 1:
            c.arrow((800, y + 105), (800, y + 145), label="依赖")
        y += 135
    return c.save("图3-3_后端分层结构.png")


def draw_er_diagram() -> Path:
    c = Canvas(2500, 1600, "核心数据库 ER 图", "字段来自 SQLAlchemy 模型，图中保留论文分析所需的主键、外键和关键业务字段")
    table_fields = {
        "users": ["id PK", "email", "password_hash", "created_at"],
        "records": ["id PK", "user_id FK", "source", "status", "created_at"],
        "record_files": ["id PK", "record_id FK", "original_filename", "display_name", "content_type", "content_bytes"],
        "ocr_results": ["id PK", "record_file_id FK", "revision_number", "is_current", "provider_name", "raw_text", "raw_payload"],
        "extracted_documents": ["id PK", "ocr_result_id FK", "record_id FK", "record_file_id FK", "document_type", "document_category", "report_date", "normalized_payload"],
        "document_versions": ["id PK", "document_id FK", "version_number", "is_current", "created_from_ocr_result_id FK", "snapshot_hash", "normalized_payload"],
        "measurements": ["id PK", "extracted_document_id FK", "document_version_id FK", "name", "value_text", "value_numeric", "unit", "observed_at"],
        "tasks": ["id PK", "user_id FK", "task_type", "resource_type", "resource_id", "status", "batch_id", "result_resource_id"],
        "task_events": ["id PK", "task_id FK", "event_type", "from_status", "to_status", "request_id", "payload"],
        "provider_events": ["id PK", "task_id FK", "user_id FK", "provider_type", "provider_name", "operation", "status", "duration_ms"],
        "audit_report_runs": ["id PK", "user_id FK", "status", "selected_document_version_ids", "graph_state", "final_report"],
        "audit_report_events": ["id PK", "run_id FK", "user_id FK", "sequence", "event_type", "node_name", "edge_source", "edge_target"],
        "audit_report_node_states": ["id PK", "run_id FK", "user_id FK", "node_name", "visit_count", "last_event_id FK", "output"],
    }
    positions = {
        "users": (80, 185),
        "records": (390, 185),
        "record_files": (700, 185),
        "ocr_results": (1010, 185),
        "extracted_documents": (1320, 185),
        "document_versions": (1655, 185),
        "measurements": (1990, 185),
        "tasks": (80, 780),
        "task_events": (420, 780),
        "provider_events": (760, 780),
        "audit_report_runs": (1130, 760),
        "audit_report_events": (1515, 720),
        "audit_report_node_states": (1515, 1080),
    }
    size = (280, 300)
    centers: dict[str, tuple[int, int]] = {}
    rects: dict[str, tuple[int, int, int, int]] = {}
    for idx, (name, fields) in enumerate(table_fields.items()):
        x, y = positions[name]
        w, h = size
        if name in {"extracted_documents", "document_versions", "ocr_results", "record_files"}:
            w, h = 310, 330
        if name in {"tasks", "provider_events", "audit_report_runs"}:
            w, h = 330, 340
        if name in {"audit_report_events", "audit_report_node_states"}:
            w, h = 340, 320
        centers[name] = (x + w // 2, y + h // 2)
        rects[name] = (x, y, x + w, y + h)
        c.draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill="#ffffff", outline="#c9d5de", width=2)
        c.draw.rounded_rectangle((x, y, x + w, y + 42), radius=18, fill=blend(PALETTE["blue"], 0.16), outline="#c9d5de", width=0)
        c.draw.text((x + 16, y + 10), name, fill=PALETTE["ink"], font=font(22, True))
        fy = y + 55
        for field in fields:
            color = PALETTE["blue"] if "PK" in field else PALETTE["green"] if "FK" in field else "#334155"
            c.draw.text((x + 18, fy), field, fill=color, font=font(16))
            fy += 24

    def port(name: str, side: str, offset: int = 0) -> tuple[int, int]:
        x1, y1, x2, y2 = rects[name]
        if side == "right":
            return (x2, (y1 + y2) // 2 + offset)
        if side == "left":
            return (x1, (y1 + y2) // 2 + offset)
        if side == "top":
            return ((x1 + x2) // 2 + offset, y1)
        return ((x1 + x2) // 2 + offset, y2)

    pipeline = ["users", "records", "record_files", "ocr_results", "extracted_documents", "document_versions", "measurements"]
    for source, target in zip(pipeline, pipeline[1:]):
        c.arrow(port(source, "right"), port(target, "left"), color=PALETTE["blue"], width=3, label="1:N")

    c.poly_arrow(
        [port("extracted_documents", "bottom"), (1475, 590), (2130, 590), port("measurements", "bottom")],
        color=PALETTE["green"],
        width=2,
        label="document_id",
    )

    c.arrow(port("users", "bottom"), port("tasks", "top"), color=PALETTE["orange"], width=3, label="1:N")
    c.arrow(port("tasks", "right"), port("task_events", "left"), color=PALETTE["orange"], width=3, label="1:N")
    c.poly_arrow(
        [port("tasks", "bottom", 80), (245, 1180), (925, 1180), port("provider_events", "bottom")],
        color=PALETTE["orange"],
        width=2,
        label="provider 调用",
    )

    c.poly_arrow(
        [port("users", "bottom"), (220, 670), (1295, 670), port("audit_report_runs", "top")],
        color=PALETTE["purple"],
        width=3,
        label="user_id",
    )
    c.arrow(port("audit_report_runs", "right"), port("audit_report_events", "left"), color=PALETTE["purple"], width=3, label="1:N")
    c.poly_arrow(
        [port("audit_report_runs", "bottom"), (1295, 1020), (1515, 1020), port("audit_report_node_states", "left")],
        color=PALETTE["purple"],
        width=3,
        label="节点状态",
    )
    c.arrow(port("audit_report_events", "bottom"), port("audit_report_node_states", "top"), color=PALETTE["muted"], width=2, label="last_event")

    c.box((1990, 760, 2330, 910), "图例", ["蓝色：资料处理主链路", "橙色：异步任务链路", "紫色：审计报告状态机链路", "字段标注 PK / FK"], fill=PALETTE["gray_soft"], accent=PALETTE["muted"])
    return c.save("图3-4_核心数据库ER图.png")


def draw_api_map() -> Path:
    groups = route_groups()
    c = Canvas(1800, 1050, "API 接口分组图", "路由来自 FastAPI APIRouter，反映当前后端真实接口边界")
    labels = [
        ("auth", "认证与当前用户"),
        ("files", "文件上传与文档关联"),
        ("ocr", "OCR 任务与版本查询"),
        ("ingestion", "标准化入库"),
        ("documents", "文档查询与维护"),
        ("measurements", "指标检索与时序"),
        ("audit-reports", "综合审计报告"),
        ("insight", "智能洞察会话"),
        ("chat", "批量分析与对话"),
        ("tasks", "任务状态与事件"),
    ]
    for idx, (name, desc) in enumerate(labels):
        row, col = divmod(idx, 5)
        x = 80 + col * 340
        y = 190 + row * 330
        count = len(groups.get(name, []))
        if name == "documents":
            count = len([item for key in ("documents", "document-versions", "records") for item in groups.get(key, [])])
        if name == "measurements":
            count = len(groups.get("measurements", []))
        c.box((x, y, x + 285, y + 220), name, [desc, f"接口数量：{count}", "认证：Bearer Token"], fill="#ffffff", accent=[PALETTE["blue"], PALETTE["green"], PALETTE["orange"], PALETTE["purple"]][idx % 4])
    c.box((650, 870, 1150, 950), "统一入口", "app.include_router(api_router, prefix='/api')", fill=PALETTE["gray_soft"], accent=PALETTE["muted"])
    return c.save("图3-5_API接口分组图.png")


def draw_security_traceability() -> Path:
    c = Canvas(1600, 920, "安全与可追溯设计", "医疗数据处理过程通过用户隔离、任务事件和审计事件实现来源可查")
    c.box((80, 250, 350, 390), "用户隔离", ["users.id", "Record.user_id", "所有查询按 user_id 过滤"], fill=PALETTE["blue_soft"], accent=PALETTE["blue"])
    c.box((470, 160, 760, 300), "原始证据", ["record_files.content_bytes", "ocr_results.raw_text", "DocumentVersion.snapshot_hash"], fill=PALETTE["green_soft"], accent=PALETTE["green"])
    c.box((470, 430, 760, 570), "任务留痕", ["tasks.status", "task_events", "provider_events"], fill=PALETTE["orange_soft"], accent=PALETTE["orange"])
    c.box((900, 250, 1210, 390), "审计留痕", ["audit_report_events", "audit_report_node_states", "final_report.evidence_items"], fill=PALETTE["purple_soft"], accent=PALETTE["purple"])
    c.box((1280, 250, 1510, 390), "前端展示", ["节点高亮", "边流转", "完整报告"], fill="#ffffff", accent=PALETTE["green"])
    c.arrow((350, 320), (470, 230), label="归属")
    c.arrow((350, 320), (470, 500), label="鉴权")
    c.arrow((760, 230), (900, 320), color=PALETTE["green"], label="证据")
    c.arrow((760, 500), (900, 320), color=PALETTE["orange"], label="过程")
    c.arrow((1210, 320), (1280, 320), color=PALETTE["purple"], label="轮询")
    return c.save("图3-6_安全与可追溯设计.png")


def draw_upload_ocr_sequence() -> Path:
    c = Canvas(1800, 980, "文件上传与 OCR 处理时序", "接口、服务、Provider 与数据库之间的真实调用关系")
    actors = ["前端", "files API", "FileUploadService", "数据库", "ocr API", "TaskProcessor", "OCRProvider"]
    x_positions = [120, 370, 650, 900, 1150, 1400, 1640]
    top = 170
    bottom = 850
    for x, actor in zip(x_positions, actors):
        c.box((x - 85, top, x + 85, top + 70), actor, "", fill="#ffffff", accent=PALETTE["blue"], title_size=17)
        c.draw.line((x, top + 75, x, bottom), fill="#d5dee6", width=2)
    messages = [
        (0, 1, 285, "POST /files/upload"),
        (1, 2, 350, "create_upload"),
        (2, 3, 415, "写入 records / record_files"),
        (0, 4, 510, "POST /ocr/files/{id}/extract"),
        (4, 5, 575, "submit_ocr_task / process_task"),
        (5, 6, 640, "extract(file_bytes)"),
        (6, 3, 715, "保存 ocr_results + provider_events"),
        (5, 3, 780, "tasks 标记 completed"),
    ]
    for s, t, y, label in messages:
        c.arrow((x_positions[s], y), (x_positions[t], y), label=label, color=PALETTE["green"] if t > s else PALETTE["orange"])
    return c.save("图4-1_文件上传与OCR处理时序.png")


def draw_normalization_versioning() -> Path:
    c = Canvas(1800, 960, "标准化与版本化入库流程", "OCR 原文经过 LLM/规则混合标准化后形成可追溯文档版本")
    nodes = [
        ("OCRResult", "raw_text / raw_payload"),
        ("NormalizationProvider", "llm_direct + rule_based_fallback"),
        ("NormalizationResult", "document_type / category / measurements"),
        ("ExtractedDocument", "当前文档投影"),
        ("DocumentVersion", "版本快照与 hash"),
        ("Measurement", "结构化指标索引"),
    ]
    coords = [(80, 360), (360, 230), (680, 360), (1000, 230), (1280, 360), (1560, 230)]
    for idx, ((title, body), (x, y)) in enumerate(zip(nodes, coords)):
        c.box((x, y, x + 210, y + 130), title, body, fill="#ffffff", accent=[PALETTE["blue"], PALETTE["purple"], PALETTE["green"], PALETTE["orange"]][idx % 4], title_size=18, body_size=15)
        if idx < len(nodes) - 1:
            c.arrow((x + 210, y + 65), (coords[idx + 1][0], coords[idx + 1][1] + 65), label=str(idx + 1))
    c.box((410, 650, 720, 760), "稳定性策略", ["LLM 失败时规则兜底", "snapshot_hash 避免重复版本", "narrative_context 不生成指标"], fill=PALETTE["green_soft"], accent=PALETTE["green"])
    c.box((1000, 650, 1320, 760), "论文可说明点", ["原文保留", "版本可追", "指标可查", "Provider 可替换"], fill=PALETTE["blue_soft"], accent=PALETTE["blue"])
    return c.save("图4-2_标准化与版本化入库流程.png")


def draw_audit_graph() -> Path:
    c = Canvas(2400, 1650, "综合审计报告 LangGraph 状态流转图", "边关系来自 AUDIT_GRAPH_EDGES，体现状态机、条件路由和回环复核")
    positions = {
        "__start__": (210, 760),
        "load_graph_state": (540, 760),
        "audit_router": (1040, 760),
        "document_quality_agent": (720, 405),
        "timeline_builder": (1080, 300),
        "measurement_consistency_agent": (1500, 410),
        "risk_agent": (1700, 760),
        "evidence_agent": (1500, 1110),
        "conflict_agent": (1080, 1235),
        "compliance_agent": (700, 1110),
        "quality_gate": (520, 540),
        "report_composer": (2040, 640),
        "citation_checker": (2040, 865),
        "safety_reviewer": (1840, 1095),
        "final_router": (1510, 1360),
        "persist_report": (1020, 1420),
        "__end__": (610, 1420),
    }

    def rect_for(name: str, pos: tuple[int, int]) -> tuple[int, int, int, int]:
        x, y = pos
        w = 250 if len(name) < 18 else 350
        h = 78
        return (x - w // 2, y - h // 2, x + w // 2, y + h // 2)

    rects = {name: rect_for(name, pos) for name, pos in positions.items()}

    def port(name: str, side: str, offset: int = 0) -> tuple[int, int]:
        x1, y1, x2, y2 = rects[name]
        if side == "right":
            return (x2, (y1 + y2) // 2 + offset)
        if side == "left":
            return (x1, (y1 + y2) // 2 + offset)
        if side == "top":
            return ((x1 + x2) // 2 + offset, y1)
        return ((x1 + x2) // 2 + offset, y2)

    routes: dict[tuple[str, str], tuple[list[tuple[int, int]], str, int, str | None]] = {
        ("__start__", "load_graph_state"): ([port("__start__", "right"), port("load_graph_state", "left")], PALETTE["muted"], 3, None),
        ("load_graph_state", "audit_router"): ([port("load_graph_state", "right"), port("audit_router", "left")], PALETTE["muted"], 3, None),
        ("audit_router", "document_quality_agent"): ([port("audit_router", "top", -90), (930, 570), port("document_quality_agent", "right", 18)], PALETTE["blue"], 3, None),
        ("document_quality_agent", "audit_router"): ([port("document_quality_agent", "right", -18), (840, 570), port("audit_router", "left", -24)], PALETTE["line"], 2, None),
        ("audit_router", "timeline_builder"): ([port("audit_router", "top", -15), port("timeline_builder", "bottom", -15)], PALETTE["blue"], 3, None),
        ("timeline_builder", "audit_router"): ([port("timeline_builder", "bottom", 35), (1160, 535), port("audit_router", "top", 40)], PALETTE["line"], 2, None),
        ("audit_router", "measurement_consistency_agent"): ([port("audit_router", "right", -28), (1270, 590), port("measurement_consistency_agent", "left", 20)], PALETTE["blue"], 3, None),
        ("measurement_consistency_agent", "audit_router"): ([port("measurement_consistency_agent", "left", -24), (1320, 650), port("audit_router", "right", -28)], PALETTE["line"], 2, None),
        ("audit_router", "risk_agent"): ([port("audit_router", "right"), port("risk_agent", "left")], PALETTE["blue"], 3, None),
        ("risk_agent", "audit_router"): ([port("risk_agent", "left", 26), (1410, 850), port("audit_router", "right", 26)], PALETTE["line"], 2, None),
        ("audit_router", "evidence_agent"): ([port("audit_router", "right", 32), (1270, 940), port("evidence_agent", "left", -24)], PALETTE["blue"], 3, None),
        ("evidence_agent", "audit_router"): ([port("evidence_agent", "left", 24), (1240, 1020), port("audit_router", "bottom", 85)], PALETTE["line"], 2, None),
        ("audit_router", "conflict_agent"): ([port("audit_router", "bottom", 55), (1130, 1000), port("conflict_agent", "top", 55)], PALETTE["blue"], 3, None),
        ("conflict_agent", "audit_router"): ([port("conflict_agent", "top", -55), (970, 1000), port("audit_router", "bottom", -55)], PALETTE["line"], 2, None),
        ("audit_router", "compliance_agent"): ([port("audit_router", "bottom", -92), (830, 980), port("compliance_agent", "right", -18)], PALETTE["blue"], 3, None),
        ("compliance_agent", "audit_router"): ([port("compliance_agent", "right", 20), (820, 1010), port("audit_router", "left", 28)], PALETTE["line"], 2, None),
        ("audit_router", "quality_gate"): ([port("audit_router", "left", -28), (700, 655), port("quality_gate", "right", 18)], PALETTE["blue"], 3, None),
        ("quality_gate", "audit_router"): ([port("quality_gate", "right", -18), (725, 705), port("audit_router", "left", 28)], PALETTE["line"], 2, None),
        ("audit_router", "report_composer"): ([port("audit_router", "right", -8), (1810, 700), port("report_composer", "left", 10)], PALETTE["purple"], 4, "审计完成"),
        ("report_composer", "citation_checker"): ([port("report_composer", "bottom"), port("citation_checker", "top")], PALETTE["orange"], 3, None),
        ("citation_checker", "safety_reviewer"): ([port("citation_checker", "bottom", -30), (1985, 1015), port("safety_reviewer", "right", -18)], PALETTE["orange"], 3, None),
        ("safety_reviewer", "final_router"): ([port("safety_reviewer", "bottom", -35), (1720, 1235), port("final_router", "top", 70)], PALETTE["orange"], 3, None),
        ("final_router", "audit_router"): ([port("final_router", "left", -8), (1260, 1490), (330, 1490), (330, 900), (880, 900), port("audit_router", "bottom", -70)], PALETTE["red"], 3, "补充审计"),
        ("final_router", "report_composer"): ([port("final_router", "right", -8), (2190, 1350), (2190, 690), port("report_composer", "right", 22)], PALETTE["orange"], 3, "重写报告"),
        ("final_router", "persist_report"): ([port("final_router", "left", 22), port("persist_report", "right")], PALETTE["green"], 4, "通过"),
        ("persist_report", "__end__"): ([port("persist_report", "left"), port("__end__", "right")], PALETTE["green"], 4, None),
    }

    for source, target in AUDIT_GRAPH_EDGES:
        if source not in positions or target not in positions:
            continue
        points, color, width, label = routes.get(
            (source, target),
            ([positions[source], positions[target]], PALETTE["muted"], 2, None),
        )
        c.poly_arrow(points, color=color, width=width, label=label)

    def node_box(name: str, xy: tuple[int, int, int, int]) -> None:
        if name in {"audit_router", "final_router"}:
            fill, accent = PALETTE["purple_soft"], PALETTE["purple"]
        elif name.startswith("__"):
            fill, accent = PALETTE["gray_soft"], PALETTE["muted"]
        elif "report" in name or "checker" in name or "reviewer" in name:
            fill, accent = PALETTE["orange_soft"], PALETTE["orange"]
        elif name in {"quality_gate", "persist_report"}:
            fill, accent = PALETTE["green_soft"], PALETTE["green"]
        else:
            fill, accent = "#ffffff", PALETTE["blue"]
        c.box(xy, name, "", fill=fill, accent=accent, title_size=18)

    for name, xy in rects.items():
        node_box(name, xy)

    c.box((1660, 170, 2260, 310), "状态机特征", ["蓝线：审计 Router 分派", "灰线：Agent 完成后回到 Router", "红线：final_router 可回环补充审计", "绿线：通过后持久化并结束"], fill="#ffffff", accent=PALETTE["red"])
    return c.save("图4-3_综合审计报告LangGraph状态流转图.png")


def draw_audit_persistence() -> Path:
    c = Canvas(1700, 980, "审计事件与节点状态持久化", "每次综合报告运行都会保留边、节点、状态和最终报告")
    c.box((100, 250, 390, 390), "AuditReportRun", ["status", "selected_document_version_ids", "graph_state", "final_report"], fill=PALETTE["blue_soft"], accent=PALETTE["blue"])
    c.box((590, 160, 900, 300), "AuditReportEvent", ["sequence", "event_type", "node_name", "edge_source", "edge_target"], fill=PALETTE["green_soft"], accent=PALETTE["green"])
    c.box((590, 460, 900, 600), "AuditReportNodeState", ["node_name", "visit_count", "last_event_id", "output"], fill=PALETTE["purple_soft"], accent=PALETTE["purple"])
    c.box((1110, 250, 1450, 390), "前端轮询展示", ["GET /audit-reports/{id}", "GET /events", "GET /nodes", "打开完整报告"], fill=PALETTE["orange_soft"], accent=PALETTE["orange"])
    c.arrow((390, 320), (590, 230), label="追加事件")
    c.arrow((390, 320), (590, 530), label="更新节点")
    c.arrow((900, 230), (1110, 320), color=PALETTE["green"], label="边高亮")
    c.arrow((900, 530), (1110, 320), color=PALETTE["purple"], label="节点状态")
    c.arrow((245, 390), (1280, 390), color=PALETTE["orange"], elbow=(245, 760), label="最终报告")
    return c.save("图4-4_审计事件与节点状态持久化.png")


def draw_frontend_modules() -> Path:
    c = Canvas(1700, 960, "前端模块结构", "模块来自 frontend/src/App.jsx 的 MODULES 配置和真实 API 封装")
    center = (850, 500)
    c.box((700, 430, 1000, 570), "HealthDoc.OS Workspace", ["统一 Token", "模块切换", "API 服务封装"], fill=PALETTE["gray_soft"], accent=PALETTE["muted"])
    modules = [
        ("系统控制台", (240, 220), PALETTE["blue"]),
        ("文档接入流程", (700, 180), PALETTE["green"]),
        ("文档库", (1170, 220), PALETTE["orange"]),
        ("综合审计报告", (1260, 660), PALETTE["purple"]),
        ("智能洞察", (700, 770), PALETTE["blue"]),
        ("指标探索", (240, 660), PALETTE["green"]),
    ]
    for title, pos, accent in modules:
        x, y = pos
        c.box((x, y, x + 240, y + 100), title, "", fill="#ffffff", accent=accent)
        c.arrow(center, (x + 120, y + 50), color=accent)
    return c.save("图4-5_前端模块结构.png")


def draw_mock_distribution() -> Path:
    summary = mock_summary()
    c = Canvas(1600, 940, "Mock 体检数据分布", "数据来自 scripts/seed_mock_exam_data.py 的 MOCK_DOCUMENTS 定义")
    c.box((90, 180, 410, 310), "文档总数", f"{summary['document_count']} 份", fill=PALETTE["blue_soft"], accent=PALETTE["blue"], title_size=24, body_size=34)
    c.box((460, 180, 780, 310), "结构化指标", f"{summary['measurement_count']} 条", fill=PALETTE["green_soft"], accent=PALETTE["green"], title_size=24, body_size=34)
    c.box((830, 180, 1150, 310), "叙事事实", f"{summary['prose_fact_count']} 条", fill=PALETTE["orange_soft"], accent=PALETTE["orange"], title_size=24, body_size=34)
    c.box((1200, 180, 1510, 310), "数据来源", "exam_mock_v1", fill=PALETTE["purple_soft"], accent=PALETTE["purple"], title_size=24, body_size=28)
    x0, y0 = 160, 430
    max_count = max(summary["document_types"].values())
    for idx, (dtype, count) in enumerate(summary["document_types"].items()):
        y = y0 + idx * 70
        bar_w = int(560 * count / max_count)
        c.draw.text((x0, y), dtype, fill=PALETTE["ink"], font=font(20, True))
        c.draw.rounded_rectangle((x0 + 260, y, x0 + 260 + bar_w, y + 30), radius=12, fill=blend(PALETTE["blue"], 0.75))
        c.draw.text((x0 + 280 + bar_w, y), str(count), fill=PALETTE["muted"], font=font(19))
    x1, y1 = 900, 430
    for idx, (month, count) in enumerate(summary["monthly_documents"].items()):
        y = y1 + idx * 70
        bar_w = int(400 * count / max(summary["monthly_documents"].values()))
        c.draw.text((x1, y), month, fill=PALETTE["ink"], font=font(20, True))
        c.draw.rounded_rectangle((x1 + 150, y, x1 + 150 + bar_w, y + 30), radius=12, fill=blend(PALETTE["green"], 0.75))
        c.draw.text((x1 + 170 + bar_w, y), str(count), fill=PALETTE["muted"], font=font(19))
    return c.save("图5-1_Mock体检数据分布.png")


def draw_test_flow_result() -> Path:
    c = Canvas(1800, 960, "端到端测试链路", "测试路径覆盖登录、上传、OCR、标准化、查询和 LangGraph 审计报告")
    steps = [
        ("登录", "/auth/login"),
        ("上传", "/files/upload"),
        ("OCR", "/ocr/files/{id}/extract"),
        ("标准化", "/ingestion/.../normalize"),
        ("查询", "/documents / measurements"),
        ("审计运行", "/audit-reports"),
        ("节点轮询", "/events / nodes"),
        ("最终报告", "final_report"),
    ]
    x = 80
    for idx, (title, body) in enumerate(steps):
        row = idx // 4
        col = idx % 4
        x = 120 + col * 410
        y = 245 + row * 310
        c.box((x, y, x + 300, y + 120), title, body, fill="#ffffff", accent=[PALETTE["blue"], PALETTE["green"], PALETTE["orange"], PALETTE["purple"]][idx % 4])
        if idx < len(steps) - 1:
            if col < 3:
                c.arrow((x + 300, y + 60), (x + 410, y + 60))
            else:
                c.arrow((x + 150, y + 120), (120 + 150, y + 310), elbow=(x + 150, y + 205))
    c.box((690, 790, 1110, 880), "验证结论", "现有 pytest：7 passed；临时后端 /api/health 返回 200。", fill=PALETTE["green_soft"], accent=PALETTE["green"])
    return c.save("图5-2_端到端测试链路.png")


def draw_er_diagram() -> Path:
    c = Canvas(2600, 1500, "核心数据库 ER 图", "按资料处理、异步任务、审计报告三条链路分区绘制，避免连接线交叉")

    table_fields = {
        "users": ["id PK", "email", "password_hash", "created_at"],
        "records": ["id PK", "user_id FK", "source", "status"],
        "record_files": ["id PK", "record_id FK", "filename", "content_type"],
        "ocr_results": ["id PK", "record_file_id FK", "revision", "raw_text"],
        "extracted_documents": ["id PK", "ocr_result_id FK", "document_type", "report_date"],
        "document_versions": ["id PK", "document_id FK", "version_number", "snapshot_hash"],
        "measurements": ["id PK", "document_version_id FK", "name", "value_numeric", "unit"],
        "tasks": ["id PK", "user_id FK", "task_type", "status", "resource_id"],
        "task_events": ["id PK", "task_id FK", "event_type", "from_status", "to_status"],
        "provider_events": ["id PK", "task_id FK", "provider_type", "operation", "duration_ms"],
        "audit_report_runs": ["id PK", "user_id FK", "status", "selected_version_ids", "final_report"],
        "audit_report_events": ["id PK", "run_id FK", "sequence", "node_name", "edge_target"],
        "audit_report_node_states": ["id PK", "run_id FK", "node_name", "visit_count", "last_event_id FK"],
    }

    positions = {
        "users": (90, 210),
        "records": (420, 210),
        "record_files": (750, 210),
        "ocr_results": (1080, 210),
        "extracted_documents": (1410, 210),
        "document_versions": (1740, 210),
        "measurements": (2070, 210),
        "tasks": (90, 780),
        "task_events": (420, 780),
        "provider_events": (750, 780),
        "audit_report_runs": (1740, 780),
        "audit_report_events": (2070, 780),
        "audit_report_node_states": (2070, 1110),
    }

    rects: dict[str, tuple[int, int, int, int]] = {}

    def draw_entity(name: str, xy: tuple[int, int], accent: str) -> None:
        x, y = xy
        w, h = 285, 245
        if name in {"extracted_documents", "document_versions", "audit_report_node_states"}:
            w = 310
        rects[name] = (x, y, x + w, y + h)
        c.box(rects[name], name, table_fields[name], fill="#ffffff", accent=accent, title_size=21, body_size=15)

    for name in ["users", "records", "record_files", "ocr_results", "extracted_documents", "document_versions", "measurements"]:
        draw_entity(name, positions[name], PALETTE["blue"])
    for name in ["tasks", "task_events", "provider_events"]:
        draw_entity(name, positions[name], PALETTE["orange"])
    for name in ["audit_report_runs", "audit_report_events", "audit_report_node_states"]:
        draw_entity(name, positions[name], PALETTE["purple"])

    def port(name: str, side: str, offset: int = 0) -> tuple[int, int]:
        x1, y1, x2, y2 = rects[name]
        if side == "right":
            return (x2, (y1 + y2) // 2 + offset)
        if side == "left":
            return (x1, (y1 + y2) // 2 + offset)
        if side == "top":
            return ((x1 + x2) // 2 + offset, y1)
        return ((x1 + x2) // 2 + offset, y2)

    def link(source: str, target: str, color: str, label: str = "1:N") -> None:
        c.poly_arrow([port(source, "right"), port(target, "left")], color=color, width=3, label=label)

    for source, target in zip(
        ["users", "records", "record_files", "ocr_results", "extracted_documents", "document_versions"],
        ["records", "record_files", "ocr_results", "extracted_documents", "document_versions", "measurements"],
    ):
        link(source, target, PALETTE["blue"])

    c.poly_arrow([port("users", "bottom"), port("tasks", "top")], color=PALETTE["orange"], width=3, label="user_id")
    link("tasks", "task_events", PALETTE["orange"])
    link("task_events", "provider_events", PALETTE["orange"], label="task_id")

    c.poly_arrow([port("document_versions", "bottom"), port("audit_report_runs", "top")], color=PALETTE["purple"], width=3, label="selected ids")
    link("audit_report_runs", "audit_report_events", PALETTE["purple"])
    c.poly_arrow([port("audit_report_events", "bottom"), port("audit_report_node_states", "top")], color=PALETTE["purple"], width=3, label="run_id")

    c.box(
        (90, 1260, 700, 1390),
        "图例",
        [
            "蓝色：资料处理主链路",
            "橙色：异步任务与 Provider 调用链路",
            "紫色：LangGraph 审计报告状态机链路",
            "字段标注 PK / FK，连接线均为一对多或引用关系",
        ],
        fill=PALETTE["gray_soft"],
        accent=PALETTE["muted"],
        title_size=20,
        body_size=16,
    )
    return c.save("图3-4_核心数据库ER图.png")


def draw_audit_graph() -> Path:
    c = Canvas(2400, 1450, "综合审计报告 LangGraph 状态流转图", "采用总线式布局展示真实状态机边关系：分派、回收、复核回环和最终持久化")

    rects: dict[str, tuple[int, int, int, int]] = {}

    def node(name: str, x: int, y: int, *, kind: str = "agent", w: int = 300) -> None:
        h = 82
        rects[name] = (x, y, x + w, y + h)
        if kind == "router":
            fill, accent = PALETTE["purple_soft"], PALETTE["purple"]
        elif kind == "report":
            fill, accent = PALETTE["orange_soft"], PALETTE["orange"]
        elif kind == "terminal":
            fill, accent = PALETTE["gray_soft"], PALETTE["muted"]
        elif kind == "persist":
            fill, accent = PALETTE["green_soft"], PALETTE["green"]
        else:
            fill, accent = "#ffffff", PALETTE["blue"]
        c.box(rects[name], name, "", fill=fill, accent=accent, title_size=18)

    def port(name: str, side: str, offset: int = 0) -> tuple[int, int]:
        x1, y1, x2, y2 = rects[name]
        if side == "right":
            return (x2, (y1 + y2) // 2 + offset)
        if side == "left":
            return (x1, (y1 + y2) // 2 + offset)
        if side == "top":
            return ((x1 + x2) // 2 + offset, y1)
        return ((x1 + x2) // 2 + offset, y2)

    node("__start__", 90, 545, kind="terminal", w=240)
    node("load_graph_state", 390, 545, w=300)
    node("audit_router", 760, 545, kind="router", w=300)

    left_agents = [
        ("document_quality_agent", 1120, 250),
        ("timeline_builder", 1120, 410),
        ("measurement_consistency_agent", 1120, 570),
        ("risk_agent", 1120, 730),
    ]
    right_agents = [
        ("evidence_agent", 1500, 250),
        ("conflict_agent", 1500, 410),
        ("compliance_agent", 1500, 570),
        ("quality_gate", 1500, 730),
    ]
    for name, x, y in left_agents + right_agents:
        node(name, x, y, kind="persist" if name == "quality_gate" else "agent", w=330)

    node("report_composer", 1900, 360, kind="report", w=300)
    node("citation_checker", 1900, 520, kind="report", w=300)
    node("safety_reviewer", 1900, 680, kind="report", w=300)
    node("final_router", 1900, 840, kind="router", w=300)
    node("persist_report", 1900, 1030, kind="persist", w=300)
    node("__end__", 1900, 1190, kind="terminal", w=300)

    c.poly_arrow([port("__start__", "right"), port("load_graph_state", "left")], color=PALETTE["muted"], width=3)
    c.poly_arrow([port("load_graph_state", "right"), port("audit_router", "left")], color=PALETTE["muted"], width=3)

    dispatch_x = 1080
    collect_x = 1870
    c.draw.line((dispatch_x, 250, dispatch_x, 812), fill=PALETTE["blue"], width=4)
    c.draw.line((collect_x, 250, collect_x, 812), fill=PALETTE["line"], width=3)
    c.poly_arrow([port("audit_router", "right"), (dispatch_x, port("audit_router", "right")[1])], color=PALETTE["blue"], width=4, label="条件分派")

    for name, _, _ in left_agents + right_agents:
        c.poly_arrow([(dispatch_x, port(name, "left")[1]), port(name, "left")], color=PALETTE["blue"], width=3)
        c.poly_arrow([port(name, "right"), (collect_x, port(name, "right")[1])], color=PALETTE["line"], width=2)

    c.poly_arrow([(collect_x, 812), (collect_x, 930), (910, 930), port("audit_router", "bottom")], color=PALETTE["line"], width=3, label="Agent 完成后回到 Router")
    c.poly_arrow([(collect_x, port("report_composer", "left")[1]), port("report_composer", "left")], color=PALETTE["purple"], width=4, label="质量门禁通过")

    for source, target in [
        ("report_composer", "citation_checker"),
        ("citation_checker", "safety_reviewer"),
        ("safety_reviewer", "final_router"),
        ("final_router", "persist_report"),
        ("persist_report", "__end__"),
    ]:
        c.poly_arrow([port(source, "bottom"), port(target, "top")], color=PALETTE["orange"] if target != "__end__" else PALETTE["green"], width=3)

    c.poly_arrow([port("final_router", "right"), (2260, 881), (2260, 401), port("report_composer", "right")], color=PALETTE["orange"], width=3, label="重写报告")
    c.poly_arrow([port("final_router", "left"), (1710, 881), (1710, 1170), (760, 1170), (760, 640), port("audit_router", "left", 30)], color=PALETTE["red"], width=3, label="补充审计")
    c.poly_arrow([port("final_router", "bottom"), port("persist_report", "top")], color=PALETTE["green"], width=4, label="通过")

    c.box(
        (90, 170, 580, 330),
        "运行含义",
        [
            "蓝色总线：audit_router 按 GraphState 分派审计 Agent",
            "灰色总线：Agent 写回状态后回到 audit_router",
            "橙色链路：报告生成、引用检查和安全审查",
            "红色回环：final_router 发现问题后回到审计阶段",
        ],
        fill="#ffffff",
        accent=PALETTE["red"],
        title_size=20,
        body_size=16,
    )
    return c.save("图4-3_综合审计报告LangGraph状态流转图.png")


def write_snapshot(paths: list[Path]) -> None:
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    payload = {
        "providers": {
            "ocr": settings.ocr_provider,
            "normalization": settings.normalization_provider,
            "llm": settings.llm_provider,
            "storage": settings.storage_provider,
        },
        "routes": route_groups(),
        "audit_graph_edges": AUDIT_GRAPH_EDGES,
        "mock_data": mock_summary(),
        "figures": [str(path.relative_to(ROOT)) for path in paths],
        "tables": {
            name: [column.name for column in table.columns]
            for name, table in sorted(Base.metadata.tables.items())
            if name
            in {
                "users",
                "records",
                "record_files",
                "ocr_results",
                "extracted_documents",
                "document_versions",
                "measurements",
                "tasks",
                "task_events",
                "provider_events",
                "audit_report_runs",
                "audit_report_events",
                "audit_report_node_states",
            }
        },
    }
    SNAPSHOT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    figure_paths = [
        draw_scenario(),
        draw_provider_architecture(),
        draw_langgraph_principle(),
        draw_system_architecture(),
        draw_business_flow(),
        draw_backend_layers(),
        draw_er_diagram(),
        draw_api_map(),
        draw_security_traceability(),
        draw_upload_ocr_sequence(),
        draw_normalization_versioning(),
        draw_audit_graph(),
        draw_audit_persistence(),
        draw_frontend_modules(),
        draw_mock_distribution(),
        draw_test_flow_result(),
    ]
    write_snapshot(figure_paths)
    print(f"generated {len(figure_paths)} figures")
    for path in figure_paths:
        print(path.relative_to(ROOT))
    print(SNAPSHOT_FILE.relative_to(ROOT))


if __name__ == "__main__":
    main()
