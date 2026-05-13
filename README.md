# MOG 医疗审计系统

面向个人健康数据管理和医疗文档审计场景的全栈产品。系统围绕体检、病历、化验文档接入、OCR、标准化入库、指标查询、智能洞察和综合审计报告生成展开；综合审计报告使用 LangGraph 状态机驱动多个 Agent 节点协作，并通过前端流程图展示真实数据流转。

## 当前核心能力

- 文档接入：文件上传、自动 OCR 路由、标准化解析、文档版本管理。
- 结构化入库：体检指标、文档原文、报告日期、文档类别与版本快照。
- 文档审阅：文档库支持查看 OCR 原文、结构化指标和标准化载荷。
- 智能洞察：基于所选文档上下文调用 LLM，提供聊天式健康分析。
- 综合审计报告：通过 LangGraph 图执行生成最终报告，包含质量审计、时间线、指标一致性、风险识别、RAG 知识检索、证据补全、冲突复核、合规审计、质量门控、报告生成、引用校验、安全复核和报告落库，前端支持导出可打印 HTML 报告。
- RAG 知识库：内置项目审计规则和《默沙东诊疗手册大众版》来源摘要知识块，落库到 `knowledge_chunks`，使用 BM25 + 关键词 + 医疗同义词混合检索，支持 `/api/knowledge/search` 返回可解释分数，并在审计报告生成链路中作为真实 GraphState 输入。
- 运行可观测：Provider 调用会记录状态、耗时和错误分类，工作台展示近 24 小时链路调用统计。
- 前端展示：React 单页应用，综合报告模块通过轮询真实 API 高亮 LangGraph 节点和边。

## 快速启动

### 后端

```bash
cp .env.example .env
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

### Mock 数据

```bash
python scripts/seed_mock_exam_data.py
python scripts/seed_msd_manual_rag.py
python scripts/check_rag_sources.py
```

默认测试账户见脚本输出；当前 mock 脚本会创建可用于综合审计报告的体检/病历/化验文档。RAG 脚本会补齐真实来源知识块，不会整站复制默沙东正文，只保存摘要化审计知识和来源 URL。来源检查脚本会联网验证这些 URL 是否仍可访问。

## 本地运行与上线配置

默认配置面向本地开发运行：启用 `/docs`、`/api-test`、启动时 schema sync，并允许常见本地前端 origin。设置 `APP_ENV=production` 后，应用会自动关闭这些开发便利项，并在启动时强制检查生产配置。

上线前至少需要设置：

```bash
APP_ENV=production
DATABASE_URL=mysql+pymysql://<user>:<password>@<host>:3306/<db>?charset=utf8mb4
AUTH_SECRET_KEY=<至少 32 位的随机密钥>
CORS_ALLOW_ORIGINS=https://your-domain.example
DOCS_ENABLED=false
ENABLE_API_TEST_PAGE=false
AUTO_SYNC_DATABASE_SCHEMA=false
UPLOAD_MAX_BYTES=20971520
UPLOAD_ALLOWED_CONTENT_TYPES=image/png,image/jpeg,application/pdf,text/plain
```

生产环境默认不执行 `ensure_database_schema()`，请使用 `alembic upgrade head` 管理数据库结构。上传接口会限制文件大小和 content type；如果需要更大的作品集演示文件，优先通过环境变量调大限制，不要改代码常量。

## 主要 API

- `POST /api/auth/register`：注册用户。
- `POST /api/auth/login`：登录并获取 token。
- `POST /api/files/upload`：上传健康档案文件。
- `POST /api/ocr/files/{record_file_id}/extract`：执行 OCR。
- `POST /api/ingestion/ocr-results/{ocr_result_id}/normalize`：标准化入库。
- `GET /api/documents`：查询文档库。
- `GET /api/documents/{document_id}`：查看文档详情、指标和标准化载荷。
- `GET /api/measurements/search`：查询结构化指标。
- `GET /api/tasks/provider-events/summary`：查看当前用户近 1 至 720 小时 Provider 调用统计。
- `POST /api/insight/sessions/stream`：创建智能洞察会话并流式返回。
- `POST /api/audit-reports`：创建综合审计报告运行。
- `POST /api/audit-reports/{run_id}/execute`：同步执行指定报告运行。
- `GET /api/audit-reports/{run_id}`：获取报告、事件流和节点状态。
- `GET /api/knowledge/chunks`：查看知识库块。
- `GET /api/knowledge/sources`：查看知识库来源统计和来源 URL。
- `GET /api/knowledge/search`：检索 RAG 知识依据。

## LangGraph 审计节点

```text
load_graph_state
  -> audit_router
  -> document_quality_agent -> audit_router
  -> timeline_builder -> audit_router
  -> measurement_consistency_agent -> audit_router
  -> risk_agent -> audit_router
  -> knowledge_retrieval_agent -> audit_router
  -> evidence_agent -> audit_router
  -> conflict_agent -> audit_router
  -> compliance_agent -> audit_router
  -> quality_gate -> audit_router
  -> report_composer -> citation_checker -> safety_reviewer -> final_router
final_router 可回到 audit_router 或 report_composer，形成可循环状态机；通过后进入 persist_report。
```

## 测试

```bash
python -m pytest -q
cd frontend
npm test
npm run build
```

## 关键目录

- `docs/INDEX.md`：文档目录索引和归档规则。
- `app/services/audit_graph/`：LangGraph 状态机、节点和 GraphState。
- `app/services/audit_report_service.py`：报告运行编排、事件落库、节点状态落库。
- `app/repositories/knowledge_repository.py`：RAG 默认知识块、落库和检索入口。
- `app/services/rag_retrieval.py`：本地可解释词法检索器。
- `frontend/src/App.jsx`：前端模块和综合报告流程图。
- `migrations/versions/`：数据库迁移。
