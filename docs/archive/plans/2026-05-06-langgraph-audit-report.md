# LangGraph Audit Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real LangGraph-backed medical audit report module with cyclic state-machine execution, persisted node events, and frontend visualization.

**Architecture:** Add a backend graph layer that reads existing document versions and measurements, executes cyclic audit nodes through LangGraph, persists run/event/report state, and exposes APIs for create/list/detail/events. Add a React module that selects documents, starts a run, polls real events, highlights graph nodes/edges, and opens the final report.

**Tech Stack:** FastAPI, SQLAlchemy, LangGraph `StateGraph`, React/Vite, node:test, pytest.

---

### Task 1: Backend Graph Contract And Models

**Files:**
- Create: `app/models/audit_report_run.py`
- Create: `app/models/audit_report_event.py`
- Create: `app/models/audit_report_node_state.py`
- Modify: `app/models/__init__.py`
- Modify: `app/core/schema.py`
- Test: `tests/test_audit_graph.py`

- [ ] Write failing tests for cyclic graph topology and persisted run/event fields.
- [ ] Add SQLAlchemy models for report runs, graph events, and node states.
- [ ] Import models in `app.models` and schema sync.
- [ ] Run `python -m pytest tests/test_audit_graph.py -q`.

### Task 2: LangGraph Audit Engine

**Files:**
- Create: `app/services/audit_graph/state.py`
- Create: `app/services/audit_graph/nodes.py`
- Create: `app/services/audit_graph/engine.py`
- Create: `app/services/audit_graph/__init__.py`
- Test: `tests/test_audit_graph.py`

- [ ] Write failing tests proving the graph can loop from citation checking back to evidence extraction.
- [ ] Implement `AuditGraphState` and node functions.
- [ ] Implement `build_audit_graph()` with conditional edges and cycle guards.
- [ ] Implement deterministic rule-based report generation so the feature works without a live LLM.

### Task 3: Repository, Service, And API

**Files:**
- Create: `app/repositories/audit_report_repository.py`
- Create: `app/services/audit_report_service.py`
- Create: `app/schemas/audit_report.py`
- Create: `app/api/v1/audit_reports.py`
- Modify: `app/api/router.py`
- Test: `tests/test_audit_graph.py`

- [ ] Write failing API/service tests for creating a run and listing ordered events.
- [ ] Persist each node transition as `node_started`, `node_completed`, `edge_traversed`, and `report_ready`.
- [ ] Expose endpoints under `/api/audit-reports`.
- [ ] Run backend tests and compile check.

### Task 4: Frontend Module

**Files:**
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/index.css`
- Modify: `frontend/tests/source-baseline.test.mjs`

- [ ] Add API client methods for audit reports.
- [ ] Add a dashboard module card for comprehensive audit report generation.
- [ ] Render document selection and a real graph visualization based on polled events.
- [ ] Render final report in a modal opened by button.
- [ ] Run `npm test` and `npm run build`.

### Task 5: Full Verification

**Files:**
- Modify only if verification exposes defects.

- [ ] Run `python -m pytest tests -q`.
- [ ] Run `python -m compileall -q app`.
- [ ] Run `npm test`.
- [ ] Run `npm run build`.
- [ ] Report any runtime verification blocked by Docker not running.
