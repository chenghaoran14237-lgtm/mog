# API 全流程 Smoke Test 报告

测试时间：2026-04-29  
测试入口：`http://127.0.0.1:5173`  
测试账号：`demo@healthdoc.local / Demo@123456`

## 结论

OpenAPI 当前暴露 50 个业务接口。已逐个覆盖认证、文件上传、OCR、标准化、文档查询、版本查询、指标查询、任务、Chat、Insight。

结果摘要：

- 非 LLM/非外部模型接口：46 次调用，46 通过，0 失败。
- 真实 OCR provider：通过，`baidu_ocr` 成功完成图片 OCR，生成 OCR result。
- LLM 相关接口：5 个业务调用失败，根因是当前 LLM 网关返回 HTML/Cloudflare 530，后端无法拿到模型响应。
- 真实标准化链路：OCR 已通过，但强制标准化失败，根因同样是 LLM 网关不可用；同时错误信息写入 `tasks.last_error_message` 时超出 255 字段长度，导致接口变成 500。
- `POST /api/tasks/{task_id}/retry` 立即响应 200，但后台重试任务没有真正跑完；日志显示容器缺少 `cryptography` 包，PyMySQL 无法用 MySQL `caching_sha2_password` 新建连接。

## 通过接口

| 接口 | 状态 |
|---|---|
| `GET /api/health` | PASS |
| `POST /api/auth/register` | PASS |
| `POST /api/auth/login` | PASS |
| `GET /api/auth/me` | PASS |
| `POST /api/files/upload` | PASS |
| `POST /api/ocr/files/{record_file_id}/extract` | PASS，复用已有 OCR 结果通过；真实图片 OCR 也通过 |
| `GET /api/ocr/files/{record_file_id}/revisions` | PASS |
| `GET /api/ocr/files/{record_file_id}/revisions/current` | PASS |
| `GET /api/ocr/revisions/{ocr_result_id}` | PASS |
| `GET /api/ocr/revisions/compare` | PASS |
| `POST /api/ingestion/ocr-results/{ocr_result_id}/normalize` | PASS，复用已有标准化结果通过；真实强制标准化失败，见问题列表 |
| `GET /api/documents` | PASS |
| `GET /api/documents/{document_id}` | PASS |
| `DELETE /api/documents/{document_id}` | PASS，使用临时文档夹具 |
| `PATCH /api/documents/{document_id}/rename` | PASS，已改名后恢复原名 |
| `GET /api/documents/{document_id}/versions` | PASS |
| `GET /api/documents/{document_id}/versions/current` | PASS |
| `GET /api/document-versions/{version_id}` | PASS |
| `GET /api/document-versions/compare` | PASS |
| `GET /api/records/{record_id}/documents` | PASS |
| `GET /api/files/{file_id}/documents` | PASS |
| `GET /api/measurements` | PASS |
| `GET /api/records/{record_id}/measurements` | PASS |
| `GET /api/files/{file_id}/measurements` | PASS |
| `GET /api/documents/{document_id}/measurements` | PASS |
| `GET /api/measurements/search` | PASS |
| `GET /api/measurements/timeseries` | PASS |
| `POST /api/query/selections` | PASS |
| `GET /api/tasks` | PASS |
| `GET /api/tasks/{task_id}` | PASS |
| `GET /api/tasks/{task_id}/events` | PASS |
| `GET /api/tasks/{task_id}/provider-events` | PASS |
| `GET /api/tasks/{task_id}/result` | PASS |
| `POST /api/tasks/{task_id}/retry` | PARTIAL，HTTP 200，但后台执行未完成，见问题列表 |
| `POST /api/chat/conversations` | PASS |
| `GET /api/chat/conversations` | PASS |
| `GET /api/chat/conversations/{conversation_id}` | PASS |
| `GET /api/chat/conversations/{conversation_id}/messages` | PASS |
| `GET /api/chat/analysis-runs` | PASS |
| `GET /api/chat/analysis-runs/{analysis_run_id}` | PASS |
| `DELETE /api/chat/analysis-runs/{analysis_run_id}` | PASS，使用临时记录夹具 |
| `GET /api/insight/sessions` | PASS |
| `GET /api/insight/sessions/{session_id}` | PASS，流式创建后可查询 |
| `GET /api/insight/sessions/{session_id}/messages` | PASS |
| `DELETE /api/insight/sessions/{session_id}` | PASS |

## 失败或不完整接口

| 接口 | 结果 | 直接原因 |
|---|---:|---|
| `POST /api/chat/conversations/{conversation_id}/messages` | FAIL 500 | LLM provider 抛出 `ProviderError` 后未被该接口捕获，直接变成 500 |
| `POST /api/chat/conversations/batch-analyze` | FAIL 503 | LLM 网关请求失败，接口正确降级为 503 |
| `POST /api/chat/conversations/batch-analyze/stream` | FAIL 200 + error event | HTTP 200，但 NDJSON 返回 `type=error`，业务未成功生成结果 |
| `POST /api/insight/sessions/stream` | FAIL 200 + error event | 会话被创建，但模型流式响应返回 `type=error` |
| `POST /api/insight/sessions/{session_id}/messages/stream` | FAIL 200 + error event | 追问消息进入流式流程，但模型响应失败 |
| `POST /api/ingestion/ocr-results/{ocr_result_id}/normalize?force=true` | FAIL 500 | LLM 标准化 provider 调用失败；随后错误消息过长，写入 `tasks.last_error_message` 触发 MySQL `Data too long` |
| `POST /api/tasks/{task_id}/retry` | PARTIAL | 接口返回 200，但后台任务连接 MySQL 时缺少 `cryptography` 包，任务停留在 `pending` |

## 建议修复顺序

1. 修 LLM 网关配置或可用性，否则 Chat、Insight、真实标准化都不会成功。
2. 给 `POST /api/chat/conversations/{conversation_id}/messages` 增加 `ProviderError` 捕获，行为应与 batch analyze 一致返回 503，而不是 500。
3. 扩大或截断 `tasks.last_error_message`，避免外部 provider 返回长 HTML 错误页时把任务状态更新也打爆。
4. 在后端镜像依赖里加入 `cryptography`，或调整 MySQL 用户认证方式，否则后台重试/异步任务新建连接会失败。

## 2026-04-29 修复后回归

已完成修复：

- `POST /api/chat/conversations/{conversation_id}/messages` 不再因 provider 异常返回 500。
- Chat、批量分析、Insight 流式接口增加兜底分析；LLM 网关不可用时返回明确标注的兜底结果，不再返回 NDJSON `type=error`。
- `llm_direct` 标准化改为混合模式：规则抽取先产出稳定基线，LLM 只做增强；LLM 失败或返回坏 JSON 时退回 `rule_based_fallback`。
- `tasks.last_error_message` 和 `task_events.message` 增加 255 字符安全截断，完整错误保留在事件 payload。
- 后端依赖加入 `cryptography`。
- `POST /api/tasks/{task_id}/retry` 使用未脱敏的数据库 URL 调度后台任务。

修复后验证：

- 本地回归测试：`python -m pytest tests/test_resilience.py -q`，3 passed。
- 语法检查：`python -m compileall -q app`，通过。
- 服务健康检查：`GET /api/health`，200。
- 关键 API 回归：19 次调用，19 passed，覆盖真实图片 OCR、标准化兜底、Chat、批量分析、Insight 流式和清理。
- retry 后台任务：新建失败任务后调用 retry，任务最终状态为 `completed`，结果为 `ocr_result:9`。
