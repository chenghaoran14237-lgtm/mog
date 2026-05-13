import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowLeft,
  Bot,
  CheckCircle2,
  Database,
  Download,
  FileSearch,
  FileText,
  Github,
  HeartPulse,
  Lock,
  LogOut,
  Mail,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  UploadCloud,
  Zap,
} from "lucide-react";
import { api } from "./services/api.js";

const MODULES = [
  {
    id: "console",
    title: "工作台",
    subtitle: "HealthDoc.OS",
    icon: HeartPulse,
    summary: "查看当前系统状态、数据资产和处理链路。",
  },
  {
    id: "intake",
    title: "文档接入流程",
    subtitle: "上传 / OCR / 标准化",
    icon: UploadCloud,
    summary: "完成医疗文档上传、OCR 提取与结构化标准化流程。",
  },
  {
    id: "vault",
    title: "文档库",
    subtitle: "OCR 结果与版本",
    icon: FileText,
    summary: "查看标准化后的文档版本、分类和报告日期。",
  },
  {
    id: "audit",
    title: "综合审计报告",
    subtitle: "LangGraph 状态机",
    icon: ShieldCheck,
    summary: "选择多份文档，启动带环路的多 Agent 审计图，生成可追溯综合报告。",
  },
  {
    id: "agent",
    title: "智能洞察",
    subtitle: "跨文档 Chatbot",
    icon: Bot,
    summary: "选择文档后发起多份报告的批量 AI 分析。",
  },
  {
    id: "rag",
    title: "RAG 知识库",
    subtitle: "默沙东来源 / 检索增强",
    icon: Database,
    summary: "查看知识库来源、检索命中和 BM25+同义词混合评分解释。",
  },
  {
    id: "metrics",
    title: "指标探索",
    subtitle: "结构化指标检索",
    icon: Activity,
    summary: "检索 measurements 表中的指标并查看趋势。",
  },
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const formatDate = (value) => (value ? new Date(value).toLocaleDateString("zh-CN") : "--");
const formatDateTime = (value) => (value ? new Date(value).toLocaleString("zh-CN") : "--");
const MAX_LOCAL_UPLOAD_BYTES = 20 * 1024 * 1024;
const ACCEPTED_UPLOAD_TYPES = "image/png,image/jpeg,application/pdf,text/plain,application/octet-stream";
const formatBytes = (value) => `${(value / 1024 / 1024).toFixed(0)} MB`;
const statusLabel = (value) =>
  ({ pending: "排队中", processing: "处理中", completed: "已完成", failed: "失败" })[value] || value || "--";
const taskLabel = (value) => ({ ocr: "OCR 识别", normalization: "标准化" })[value] || value || "--";
const categoryLabel = (value) =>
  ({ structured_metrics: "结构化指标", narrative_context: "病历叙事" })[value] || value || "--";
const documentTitle = (doc) => doc?.display_name || `文件 ${doc?.record_file_id ?? "--"}`;
const metricDisplayValue = (metric) => {
  const value =
    metric?.value_text || (metric?.value_numeric !== null && metric?.value_numeric !== undefined ? String(metric.value_numeric) : "--");
  return `${value}${metric?.unit ? ` ${metric.unit}` : ""}`;
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    const replacements = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return replacements[char];
  });
}

function downloadAuditReport(report) {
  const sections = (report.sections || [])
    .map(
      (section) => `
        <section>
          <h2>${escapeHtml(section.title || "报告段落")}</h2>
          <p>${escapeHtml(section.content || "")}</p>
        </section>`,
    )
    .join("");
  const evidence = (report.evidence_items || [])
    .map((item) => `<li><strong>${escapeHtml(item.id || item.source_label || "证据")}</strong>${escapeHtml(item.quote || "")}</li>`)
    .join("");
  const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(report.title || "综合审计报告")}</title>
  <style>
    body { margin: 0; padding: 48px; color: #18181b; font: 14px/1.75 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width: 860px; margin: 0 auto; }
    h1 { margin: 0; font-size: 28px; }
    .meta { margin: 8px 0 26px; color: #71717a; }
    .summary { padding: 16px 18px; border: 1px solid #e4e4e7; border-radius: 14px; background: #fafafa; }
    h2 { margin: 28px 0 8px; font-size: 18px; }
    p { white-space: pre-wrap; }
    li { margin: 8px 0; }
    strong { margin-right: 6px; }
    @media print { body { padding: 24px; } }
  </style>
</head>
<body>
  <main>
    <h1>${escapeHtml(report.title || "综合审计报告")}</h1>
    <div class="meta">${escapeHtml(report.generated_at ? formatDateTime(report.generated_at) : "已生成")}</div>
    <p class="summary">${escapeHtml(report.summary || "")}</p>
    ${sections}
    <section>
      <h2>证据清单</h2>
      <ol>${evidence || "<li>暂无证据项</li>"}</ol>
    </section>
  </main>
</body>
</html>`;
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const filename = `${(report.title || "综合审计报告").replace(/[\\/:*?"<>|]+/g, "_")}.html`;
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

async function waitTask(taskId, timeoutMs = 180000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const task = await api.tasks.getStatus(taskId);
    if (task.status === "completed") return task;
    if (task.status === "failed") throw new Error(task.last_error_message || `任务 ${taskId} 执行失败`);
    await sleep(700);
  }
  throw new Error(`任务 ${taskId} 执行超时`);
}

function classNames(...items) {
  return items.filter(Boolean).join(" ");
}

export default function App() {
  const [booting, setBooting] = useState(true);
  const [user, setUser] = useState(null);

  useEffect(() => {
    api.onUnauthorized(() => {
      api.setToken(null);
      setUser(null);
    });

    if (!api.getToken()) {
      setBooting(false);
      return () => api.onUnauthorized(null);
    }

    api.auth
      .me()
      .then(setUser)
      .catch(() => {
        api.setToken(null);
        setUser(null);
      })
      .finally(() => setBooting(false));

    return () => api.onUnauthorized(null);
  }, []);

  async function handleLogin(token) {
    api.setToken(token);
    const profile = await api.auth.me();
    setUser(profile);
  }

  function handleLogout() {
    api.setToken(null);
    setUser(null);
  }

  if (booting) {
    return (
      <div className="boot-screen">
        <span className="spinner" />
        正在加载工作区...
      </div>
    );
  }

  return user ? <Workspace currentUser={user} onLogout={handleLogout} /> : <LoginScreen onLogin={handleLogin} />;
}

function LoginScreen({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [noticeType, setNoticeType] = useState("error");

  async function submit(event) {
    event.preventDefault();
    setNotice("");
    setLoading(true);
    try {
      if (mode === "login") {
        const response = await api.auth.login(email, password);
        await onLogin(response.access_token);
      } else {
        await api.auth.register(email, password);
        setPassword("");
        setMode("login");
        setNoticeType("success");
        setNotice("注册完成，请登录继续。");
      }
    } catch (error) {
      setNoticeType("error");
      setNotice(error.status === 409 ? "该邮箱已注册，请直接登录。" : error.message || "请求失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-screen notranslate" translate="no">
      <div className="bg-dot-pattern" />
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      <section className="login-card">
        <aside className="login-hero">
          <div className="noise-overlay" />
          <div className="brand-row">
            <span className="brand-mark">
              <HeartPulse size={16} />
            </span>
            <span className="brand-name">
              HealthDoc<span>.OS</span>
            </span>
          </div>

          <div className="hero-copy">
            <span className="system-pill">
              <Zap size={12} />
              系统已初始化
            </span>
            <h1>
              一体化健康数据
              <br />
              <span>接入与洞察工作台</span>
            </h1>
            <p>在同一工作流中完成医疗报告上传、OCR 提取、结构化标准化、 指标检索与跨文档智能分析。</p>
            <div className="feature-list">
              <FeatureItem icon={<FileSearch />} text="OCR 提取与结构化标准化" />
              <FeatureItem icon={<Database />} text="跨文档指标索引与检索" />
              <FeatureItem icon={<Bot />} text="多份报告的批量 AI 分析" />
            </div>
          </div>

          <div className="hero-footer">
            <span>
              <i className="online-dot" />
              系统运行正常
            </span>
            <span>v2.0.4</span>
            <span>
              <Lock size={12} />
              端到端加密
            </span>
          </div>
        </aside>

        <main className="login-form-panel">
          <div className="auth-toggle">
            <button className={mode === "login" ? "active" : ""} type="button" onClick={() => setMode("login")}>
              登录
            </button>
            <button className={mode === "register" ? "active" : ""} type="button" onClick={() => setMode("register")}>
              注册
            </button>
          </div>

          <h2>{mode === "login" ? "欢迎回来" : "创建你的工作台账号"}</h2>
          <p className="muted">
            {mode === "login" ? "输入账号信息，进入系统主控台。" : "先注册一个新用户，再登录并开始数据处理流程。"}
          </p>

          <form className="stack" onSubmit={submit}>
            {mode === "register" ? (
              <label className="field">
                <span>机构 / 姓名</span>
                <input value={name} onChange={(event) => setName(event.target.value)} placeholder="请输入你的姓名" />
              </label>
            ) : null}

            <label className="field">
              <span>邮箱地址</span>
              <div className="input-icon">
                <Mail size={16} />
                <input
                  required
                  type="email"
                  placeholder="admin@example.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>
            </label>

            <label className="field">
              <span className="field-row">
                密码
                {mode === "login" ? <em>安全访问</em> : null}
              </span>
              <div className="input-icon">
                <Lock size={16} />
                <input
                  required
                  type="password"
                  placeholder="至少 8 位字符"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </div>
            </label>

            {notice ? <div className={`notice ${noticeType}`}>{notice}</div> : null}

            <button className="primary-button" disabled={loading} type="submit">
              {loading ? <span className="spinner tiny" /> : <ArrowLeft className="flip" size={16} />}
              {loading ? "处理中..." : mode === "login" ? "进入主控台" : "创建账号"}
            </button>
          </form>

          <div className="oauth-separator">或继续使用</div>
          <div className="oauth-row">
            <button type="button">
              <Github size={16} />
              GitHub
            </button>
            <button type="button">
              <GoogleIcon />
              Google
            </button>
          </div>
        </main>
      </section>
    </div>
  );
}

function FeatureItem({ icon, text }) {
  return (
    <div className="feature-item">
      {React.cloneElement(icon, { size: 14 })}
      <span>{text}</span>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}

function Workspace({ currentUser, onLogout }) {
  const [activeModule, setActiveModule] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [documentError, setDocumentError] = useState("");
  const [providerStats, setProviderStats] = useState([]);
  const [providerStatsError, setProviderStatsError] = useState("");
  const [clock, setClock] = useState("");

  useEffect(() => {
    const update = () => setClock(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, []);

  async function loadDocuments() {
    setDocumentLoading(true);
    setDocumentError("");
    try {
      const response = await api.documents.list({ page: 1, page_size: 100, sort_by: "report_date", sort_order: "desc" });
      setDocuments(response.items || []);
    } catch (error) {
      setDocumentError(error.message || "加载文档失败");
    } finally {
      setDocumentLoading(false);
    }
  }

  async function loadProviderStats() {
    setProviderStatsError("");
    try {
      const response = await api.tasks.providerSummary({ window_hours: 24 });
      setProviderStats(response.items || []);
    } catch (error) {
      setProviderStatsError(error.message || "运行统计加载失败");
    }
  }

  useEffect(() => {
    loadDocuments();
    loadProviderStats();
  }, []);

  const moduleTitle = activeModule ? MODULES.find((item) => item.id === activeModule)?.title : "工作台";
  const activeConfig = MODULES.find((item) => item.id === activeModule);

  return (
    <div className="workspace-shell">
      <div className="noise-overlay" />
      <div className="bg-dot-pattern soft" />
      <div className={classNames("ambient workspace-ambient", activeModule ? "muted" : "blue")} />

      <nav className="top-nav">
        <div className="nav-brand">
          <span className="nav-mark">
            <HeartPulse size={14} />
          </span>
          <span>
            HealthDoc<span>.OS</span>
          </span>
        </div>
        <div className="nav-status">
          <span>
            <i className="online-dot" />
            系统在线
          </span>
          <span className="hide-sm">
            <FileText size={12} />
            {documentLoading ? "..." : `${documents.length} 份文档`}
          </span>
          <span className="hide-md">{currentUser?.email}</span>
          <span>{clock}</span>
        </div>
        <button className="logout-button" onClick={onLogout} type="button">
          <LogOut size={13} />
          退出登录
        </button>
      </nav>

      <main className="workspace-main">
        {activeModule ? (
          <section className="module-dialog">
            <header className="module-header">
              <button className="back-button" onClick={() => setActiveModule(null)} type="button">
                <ArrowLeft size={16} />
              </button>
              <div>
                <h2>{moduleTitle}</h2>
                <p>{activeConfig?.subtitle}</p>
              </div>
              <button className="ghost-button" onClick={loadDocuments} type="button">
                刷新文档
              </button>
            </header>
            <div className="module-body">
              {activeModule === "intake" ? <IntakeModule onDocumentsChanged={loadDocuments} /> : null}
              {activeModule === "vault" ? (
                <VaultModule documents={documents} loading={documentLoading} error={documentError} onRefresh={loadDocuments} />
              ) : null}
              {activeModule === "audit" ? (
                <AuditReportModule documents={documents} loadingDocuments={documentLoading} onRefreshDocuments={loadDocuments} />
              ) : null}
              {activeModule === "agent" ? <InsightModule documents={documents} loadingDocuments={documentLoading} /> : null}
              {activeModule === "rag" ? <RagKnowledgeModule /> : null}
              {activeModule === "metrics" ? <MetricsModule /> : null}
            </div>
          </section>
        ) : (
          <ConsoleHome
            currentUser={currentUser}
            documents={documents}
            loading={documentLoading}
            error={documentError}
            providerStats={providerStats}
            providerStatsError={providerStatsError}
            onOpen={setActiveModule}
          />
        )}
      </main>
    </div>
  );
}

function ConsoleHome({ currentUser, documents, loading, error, providerStats, providerStatsError, onOpen }) {
  const structuredCount = documents.filter((item) => item.document_category === "structured_metrics").length;
  const narrativeCount = documents.filter((item) => item.document_category === "narrative_context").length;
  const providerEventCount = providerStats.reduce((sum, item) => sum + (item.event_count || 0), 0);
  const providerFailedCount = providerStats
    .filter((item) => item.status === "failed")
    .reduce((sum, item) => sum + (item.event_count || 0), 0);

  return (
    <section className="console-home">
      <div className="console-copy">
        <div>
          <span className="eyebrow">HEALTHDOC OS / WORKSPACE</span>
          <p>医疗资料智能管理与审计工作台。</p>
        </div>
        <span className="console-badge">{loading ? "文档加载中" : `${documents.length} 份文档`}</span>
      </div>

      <div className="metric-grid">
        <StatCard label="当前用户" value={currentUser?.email || "--"} helper="已登录工作区" />
        <StatCard label="文档总数" value={loading ? "..." : documents.length} helper={error || "资料库已同步"} />
        <StatCard label="结构化指标" value={structuredCount} helper="可用于趋势与检索" />
        <StatCard label="病历叙事" value={narrativeCount} helper="可用于智能洞察上下文" />
        <StatCard
          label="近 24h 链路调用"
          value={providerEventCount}
          helper={providerStatsError || (providerFailedCount ? `${providerFailedCount} 次异常` : "运行链路可追踪")}
        />
      </div>

      <div className="module-grid">
        {MODULES.filter((item) => item.id !== "console").map((module) => {
          const Icon = module.icon;
          return (
            <button className="module-card" key={module.id} onClick={() => onOpen(module.id)} type="button">
              <span className="module-icon">
                <Icon size={18} />
              </span>
              <span>
                <strong>{module.title}</strong>
                <em>{module.subtitle}</em>
                <small>{module.summary}</small>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function StatCard({ label, value, helper }) {
  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{helper}</small>
    </div>
  );
}

function IntakeModule({ onDocumentsChanged }) {
  const [file, setFile] = useState(null);
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [steps, setSteps] = useState([]);
  const [message, setMessage] = useState("");

  function pushStep(step) {
    setSteps((items) => [...items, { id: `${Date.now()}-${items.length}`, ...step }]);
  }

  async function runPipeline() {
    if (!file) {
      setMessage("请先选择一个文件。");
      return;
    }
    if (file.size > MAX_LOCAL_UPLOAD_BYTES) {
      setMessage(`文件过大，请选择不超过 ${formatBytes(MAX_LOCAL_UPLOAD_BYTES)} 的文件。`);
      return;
    }
    setBusy(true);
    setMessage("");
    setSteps([]);

    try {
      pushStep({ title: "文件上传", status: "processing", detail: file.name });
      const upload = await api.files.upload(file, displayName.trim() || file.name);
      pushStep({ title: "文件上传", status: "completed", detail: `record_file_id=${upload.file.id}` });

      pushStep({ title: "OCR 提取", status: "processing", detail: "调用 /ocr/files/{id}/extract" });
      const ocrTask = await api.ocr.extract(upload.file.id);
      const completedOcrTask = await waitTask(ocrTask.task.id);
      const ocrResult = await api.tasks.getResult(completedOcrTask.id);
      const ocrResultId = ocrResult.data.id;
      pushStep({ title: "OCR 提取", status: "completed", detail: `ocr_result_id=${ocrResultId}` });

      pushStep({ title: "结构化标准化", status: "processing", detail: "调用 /ingestion/ocr-results/{id}/normalize" });
      const normalizeTask = await api.ingestion.normalize(ocrResultId);
      const completedNormalizeTask = await waitTask(normalizeTask.task.id);
      const normalized = await api.tasks.getResult(completedNormalizeTask.id);
      pushStep({
        title: "结构化标准化",
        status: "completed",
        detail: `document_version_id=${normalized.data.version.id}`,
      });

      setMessage("处理完成，文档库已可查看。");
      onDocumentsChanged?.();
    } catch (error) {
      pushStep({ title: "流程失败", status: "failed", detail: error.message || "未知错误" });
      setMessage(error.message || "处理失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="two-column">
      <section className="panel">
        <h3>文档接入流程</h3>
        <p className="muted">上传文件后顺序执行 OCR 提取与结构化标准化，形成可追溯的健康资料版本。</p>

        <label className="dropzone">
          <UploadCloud size={28} />
          <strong>{file ? file.name : "选择医疗报告文件"}</strong>
          <span>支持图片、PDF 或文本输入，单文件不超过 {formatBytes(MAX_LOCAL_UPLOAD_BYTES)}</span>
          <input
            type="file"
            accept={ACCEPTED_UPLOAD_TYPES}
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </label>

        <label className="field">
          <span>显示名称</span>
          <input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder={file?.name || "例如：2026-04-12 血常规报告"}
          />
        </label>

        {message ? <div className="notice neutral">{message}</div> : null}
        <button className="primary-button" disabled={busy} onClick={runPipeline} type="button">
          {busy ? <span className="spinner tiny" /> : <CheckCircle2 size={16} />}
          {busy ? "处理中..." : "开始 OCR 提取与结构化标准化"}
        </button>
      </section>

      <section className="panel">
        <h3>任务流转</h3>
        <div className="step-list">
          {steps.length === 0 ? (
            <p className="empty">等待开始上传处理。</p>
          ) : (
            steps.map((step) => (
              <div className={`step-item ${step.status}`} key={step.id}>
                <span />
                <div>
                  <strong>{step.title}</strong>
                  <small>{step.detail}</small>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

function VaultModule({ documents, loading, error, onRefresh }) {
  const [reviewState, setReviewState] = useState({
    open: false,
    fallbackDoc: null,
    detail: null,
    ocr: null,
    loading: false,
    error: "",
  });
  const reviewRequestRef = useRef(0);

  async function openReview(doc) {
    const requestId = reviewRequestRef.current + 1;
    reviewRequestRef.current = requestId;
    setReviewState({
      open: true,
      fallbackDoc: doc,
      detail: null,
      ocr: null,
      loading: true,
      error: "",
    });
    try {
      const detail = await api.documents.getById(doc.id);
      const ocrResultId = detail.current_ocr_result_id || detail.ocr_result_id;
      const ocr = ocrResultId ? await api.ocr.getRevision(ocrResultId) : null;
      if (reviewRequestRef.current !== requestId) return;
      setReviewState({
        open: true,
        fallbackDoc: doc,
        detail,
        ocr,
        loading: false,
        error: "",
      });
    } catch (err) {
      if (reviewRequestRef.current !== requestId) return;
      setReviewState((state) => ({
        ...state,
        loading: false,
        error: err.message || "加载文档审阅详情失败",
      }));
    }
  }

  function closeReview() {
    reviewRequestRef.current += 1;
    setReviewState((state) => ({ ...state, open: false }));
  }

  return (
    <section className="panel full">
      <div className="section-toolbar">
        <div>
          <h3>文档库</h3>
          <p className="muted">展示已标准化文档和当前版本。</p>
        </div>
        <button className="ghost-button" onClick={onRefresh} type="button">
          刷新
        </button>
      </div>
      {error ? <div className="notice error">{error}</div> : null}
      <div className="document-grid">
        {loading ? <p className="empty">加载文档中...</p> : null}
        {!loading && documents.length === 0 ? <p className="empty">暂无文档。</p> : null}
        {documents.map((doc) => (
          <button className="document-card document-card-button" key={doc.id} onClick={() => openReview(doc)} type="button">
            <div className="doc-icon">{doc.document_category === "structured_metrics" ? "验" : "病"}</div>
            <div>
              <h4>{documentTitle(doc)}</h4>
              <p>{categoryLabel(doc.document_category)}</p>
              <small>版本 ID：{doc.current_version_id || "--"}</small>
              <small>
                报告日期 {formatDate(doc.report_date)} | 上传于 {formatDate(doc.uploaded_at || doc.created_at)}
              </small>
            </div>
          </button>
        ))}
      </div>
      {reviewState.open ? (
        <DocumentReviewModal
          detail={reviewState.detail}
          error={reviewState.error}
          fallbackDoc={reviewState.fallbackDoc}
          loading={reviewState.loading}
          ocr={reviewState.ocr}
          onClose={closeReview}
        />
      ) : null}
    </section>
  );
}

function DocumentReviewModal({ detail, fallbackDoc, ocr, loading, error, onClose }) {
  const doc = detail || fallbackDoc || {};
  const measurements = detail?.measurements || [];
  const normalizedPayload = detail?.normalized_payload || {};
  const rawText = ocr?.raw_text || "";

  return (
    <div className="report-modal-backdrop" role="presentation" onClick={onClose}>
      <article
        className="report-modal document-review-modal"
        role="dialog"
        aria-modal="true"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2>{documentTitle(doc)}</h2>
            <p>
              {categoryLabel(doc.document_category)} | 版本 {doc.current_version_number || "--"} | 报告日期 {formatDate(doc.report_date)}
            </p>
          </div>
          <button className="ghost-button" onClick={onClose} type="button">
            关闭
          </button>
        </header>
        <div className="report-content">
          {error ? <div className="notice error">{error}</div> : null}
          {loading ? (
            <div className="review-loading">
              <span className="spinner tiny" />
              加载审阅详情...
            </div>
          ) : (
            <>
              <div className="review-meta">
                <span>OCR：{ocr?.provider_name || "--"}</span>
                <span>修订：{ocr?.revision_number || "--"}</span>
                <span>指标：{measurements.length}</span>
                <span>文件 ID：{doc.record_file_id || "--"}</span>
              </div>
              <div className="review-grid">
                <section className="review-panel">
                  <h3>OCR 原文</h3>
                  <pre className="review-pre">{rawText || "暂无 OCR 原文。"}</pre>
                </section>
                <section className="review-panel">
                  <h3>结构化指标</h3>
                  {measurements.length === 0 ? <p className="empty">暂无结构化指标。</p> : null}
                  <div className="review-metric-list">
                    {measurements.map((metric) => (
                      <div className="review-metric-row" key={metric.id}>
                        <strong>{metric.name}</strong>
                        <span>{metricDisplayValue(metric)}</span>
                        <small>{formatDate(metric.observed_at)}</small>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
              <details className="review-payload">
                <summary>标准化载荷</summary>
                <pre className="review-pre">{JSON.stringify(normalizedPayload, null, 2)}</pre>
              </details>
            </>
          )}
        </div>
      </article>
    </div>
  );
}

const AUDIT_GRAPH_NODES = [
  { id: "load_graph_state", label: "读取状态", x: 10, y: 48 },
  { id: "audit_router", label: "审计路由器", x: 25, y: 48 },
  { id: "document_quality_agent", label: "质量审计", x: 42, y: 16 },
  { id: "timeline_builder", label: "时间线构建", x: 42, y: 34 },
  { id: "measurement_consistency_agent", label: "指标一致性", x: 42, y: 52 },
  { id: "risk_agent", label: "风险 Agent", x: 42, y: 70 },
  { id: "knowledge_retrieval_agent", label: "知识检索 RAG", x: 58, y: 18 },
  { id: "evidence_agent", label: "证据补全", x: 61, y: 35 },
  { id: "conflict_agent", label: "冲突复核", x: 61, y: 52 },
  { id: "compliance_agent", label: "合规审计", x: 61, y: 70 },
  { id: "quality_gate", label: "质量门控", x: 75, y: 48 },
  { id: "report_composer", label: "报告生成", x: 86, y: 30 },
  { id: "citation_checker", label: "引用校验", x: 86, y: 48 },
  { id: "safety_reviewer", label: "安全复核", x: 86, y: 66 },
  { id: "final_router", label: "最终路由", x: 74, y: 84 },
  { id: "persist_report", label: "报告落库", x: 92, y: 84 },
];

const AUDIT_GRAPH_EDGES = [
  ["load_graph_state", "audit_router"],
  ["audit_router", "document_quality_agent"],
  ["document_quality_agent", "audit_router"],
  ["audit_router", "timeline_builder"],
  ["timeline_builder", "audit_router"],
  ["audit_router", "measurement_consistency_agent"],
  ["measurement_consistency_agent", "audit_router"],
  ["audit_router", "risk_agent"],
  ["risk_agent", "audit_router"],
  ["audit_router", "knowledge_retrieval_agent"],
  ["knowledge_retrieval_agent", "audit_router"],
  ["audit_router", "evidence_agent"],
  ["evidence_agent", "audit_router"],
  ["audit_router", "conflict_agent"],
  ["conflict_agent", "audit_router"],
  ["audit_router", "compliance_agent"],
  ["compliance_agent", "audit_router"],
  ["audit_router", "quality_gate"],
  ["quality_gate", "audit_router"],
  ["audit_router", "report_composer"],
  ["report_composer", "citation_checker"],
  ["citation_checker", "safety_reviewer"],
  ["safety_reviewer", "final_router"],
  ["final_router", "audit_router"],
  ["final_router", "report_composer"],
  ["final_router", "persist_report"],
];

const auditStatusText = (value) =>
  ({ pending: "排队中", processing: "图执行中", completed: "报告已生成", failed: "执行失败" })[value] || "未启动";

function AuditReportModule({ documents, loadingDocuments, onRefreshDocuments }) {
  const [selected, setSelected] = useState([]);
  const [run, setRun] = useState(null);
  const [events, setEvents] = useState([]);
  const [nodeStates, setNodeStates] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reportOpen, setReportOpen] = useState(false);

  useEffect(() => {
    if (!run?.id) return undefined;
    let cancelled = false;
    let timer = null;

    async function poll() {
      try {
        const detail = await api.auditReports.get(run.id);
        if (cancelled) return;
        setRun(detail.run);
        setEvents(detail.events || []);
        setNodeStates(detail.node_states || []);
        if (!["completed", "failed"].includes(detail.run?.status)) {
          timer = setTimeout(poll, 700);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "获取审计流转状态失败");
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [run?.id]);

  function toggleDoc(versionId) {
    setSelected((items) => (items.includes(versionId) ? items.filter((id) => id !== versionId) : [...items, versionId]));
  }

  async function startRun() {
    if (selected.length === 0) {
      setError("请至少选择一份文档。");
      return;
    }
    setBusy(true);
    setError("");
    setEvents([]);
    setNodeStates([]);
    setReportOpen(false);
    try {
      const created = await api.auditReports.create(selected);
      setRun(created);
    } catch (err) {
      setError(err.message || "启动综合审计报告失败");
    } finally {
      setBusy(false);
    }
  }

  const terminal = ["completed", "failed"].includes(run?.status);

  return (
    <div className="audit-layout">
      <section className="panel audit-source-panel">
        <div className="section-toolbar compact-toolbar">
          <div>
            <h3>文档选择</h3>
            <p className="muted">{loadingDocuments ? "正在加载文档" : `可选 ${documents.length} 份`}</p>
          </div>
          <button className="ghost-button" onClick={onRefreshDocuments} type="button">
            刷新
          </button>
        </div>
        <div className="source-list audit-source-list">
          {loadingDocuments ? <p className="empty">加载文档中...</p> : null}
          {!loadingDocuments && documents.length === 0 ? <p className="empty">暂无可审计文档。</p> : null}
          {documents.map((doc) => {
            const versionId = doc.current_version_id;
            return (
              <label className="source-item audit-source-item" key={doc.id}>
                <input
                  checked={selected.includes(versionId)}
                  disabled={busy || !versionId || run?.status === "processing"}
                  type="checkbox"
                  onChange={() => toggleDoc(versionId)}
                />
                <span>
                  <strong>{documentTitle(doc)}</strong>
                  <small>{categoryLabel(doc.document_category)}</small>
                  <small>版本 ID：{versionId || "--"}</small>
                </span>
              </label>
            );
          })}
        </div>
        <button className="primary-button full-width" disabled={busy || run?.status === "processing"} onClick={startRun} type="button">
          <ShieldCheck size={15} />
          {busy ? "启动中..." : "启动 LangGraph 审计"}
        </button>
        {error ? <p className="error-text">{error}</p> : null}
      </section>

      <section className="panel audit-graph-panel">
        <div className="audit-graph-head">
          <div>
            <h3>LangGraph 状态机流转</h3>
            <p className="muted">
              {run ? `运行 #${run.id} · ${auditStatusText(run.status)} · ${events.length} 条事件` : "选择文档后启动真实图执行"}
            </p>
          </div>
          <button className="primary-button compact" disabled={!run?.final_report} onClick={() => setReportOpen(true)} type="button">
            打开完整报告
          </button>
        </div>
        <div className="audit-graph-scroll">
          <AuditGraphCanvas events={events} nodeStates={nodeStates} status={run?.status} />
        </div>
        {terminal && run?.status === "failed" ? <p className="error-text">{run.error_message || "审计图执行失败"}</p> : null}
      </section>

      {reportOpen && run?.final_report ? <AuditReportModal report={run.final_report} onClose={() => setReportOpen(false)} /> : null}
    </div>
  );
}

function AuditGraphCanvas({ events, nodeStates, status }) {
  const nodeStatus = new Map();
  const visitCount = new Map();
  const activeEdges = new Set();
  let lastEdgeKey = "";

  nodeStates.forEach((state) => {
    nodeStatus.set(state.node_name, state.status);
    visitCount.set(state.node_name, state.visit_count);
  });
  events.forEach((event) => {
    if (event.event_type === "edge_traversed" && event.edge_source && event.edge_target) {
      const key = `${event.edge_source}->${event.edge_target}`;
      activeEdges.add(key);
      lastEdgeKey = key;
    }
    if (event.event_type === "node_started" && event.node_name) nodeStatus.set(event.node_name, "processing");
    if (event.event_type === "node_completed" && event.node_name) nodeStatus.set(event.node_name, "completed");
  });

  const latestNode = [...events].reverse().find((event) => event.node_name)?.node_name;

  return (
    <div className="audit-graph-canvas">
      <svg className="audit-edges" viewBox="0 0 1000 620" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <marker id="auditArrow" markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4">
            <path d="M 0 0 L 8 4 L 0 8 z" />
          </marker>
        </defs>
        {AUDIT_GRAPH_EDGES.map(([from, to]) => {
          const key = `${from}->${to}`;
          return (
            <path
              className={classNames("audit-edge", activeEdges.has(key) && "active", key === lastEdgeKey && "latest")}
              d={auditEdgePath(from, to)}
              key={key}
              markerEnd="url(#auditArrow)"
            />
          );
        })}
      </svg>
      {AUDIT_GRAPH_NODES.map((node) => {
        const currentStatus = nodeStatus.get(node.id) || "idle";
        return (
          <div
            className={classNames("audit-node", currentStatus, latestNode === node.id && status === "processing" && "current")}
            key={node.id}
            style={{ left: `${node.x}%`, top: `${node.y}%` }}
          >
            <span>{node.label}</span>
            <small>{visitCount.get(node.id) ? `x${visitCount.get(node.id)}` : node.id}</small>
          </div>
        );
      })}
    </div>
  );
}

function auditEdgePath(from, to) {
  const source = AUDIT_GRAPH_NODES.find((node) => node.id === from);
  const target = AUDIT_GRAPH_NODES.find((node) => node.id === to);
  if (!source || !target) return "";
  const sx = source.x * 10;
  const sy = source.y * 6.2;
  const tx = target.x * 10;
  const ty = target.y * 6.2;
  const dx = tx - sx;
  const curve = Math.max(50, Math.abs(dx) * 0.42);
  if (from === "final_router" && to === "audit_router") {
    return `M ${sx} ${sy} C ${sx - 160} ${sy + 80}, ${tx - 120} ${ty + 80}, ${tx} ${ty}`;
  }
  return `M ${sx} ${sy} C ${sx + curve} ${sy}, ${tx - curve} ${ty}, ${tx} ${ty}`;
}

function AuditReportModal({ report, onClose }) {
  const knowledgeSources = report.knowledge_sources || [];
  const ragSummary = report.rag_summary || {};
  const evidenceItems = report.evidence_items || [];
  const knowledgeEvidence = evidenceItems.filter((item) => item.kind === "knowledge_chunk");
  const documentEvidence = evidenceItems.filter((item) => item.kind !== "knowledge_chunk");

  return (
    <div className="report-modal-backdrop" role="presentation" onClick={onClose}>
      <article className="report-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <h2>{report.title || "综合审计报告"}</h2>
            <p>{report.generated_at ? formatDateTime(report.generated_at) : "已生成"}</p>
          </div>
          <div className="modal-actions">
            <button className="ghost-button" onClick={() => downloadAuditReport(report)} type="button">
              <Download size={14} />
              导出报告
            </button>
            <button className="ghost-button" onClick={onClose} type="button">
              关闭
            </button>
          </div>
        </header>
        <div className="report-content">
          <p className="report-summary">{report.summary}</p>
          {knowledgeSources.length ? (
            <section className="rag-source-panel">
              <div className="rag-source-metrics">
                <span>RAG 查询 {ragSummary.query_count ?? "--"}</span>
                <span>命中知识 {ragSummary.context_count ?? knowledgeSources.length}</span>
                <span>默沙东来源 {ragSummary.msd_manual_count ?? "--"}</span>
              </div>
              <div className="rag-source-list">
                {knowledgeSources.map((source) => (
                  <div className="rag-source-card" key={source.source_url || `${source.source_title}-${source.section_title}`}>
                    <span>{source.source_name || "知识来源"}</span>
                    <strong>{source.section_title || source.source_title}</strong>
                    {source.source_url ? (
                      <a href={source.source_url} rel="noreferrer" target="_blank">
                        查看来源
                      </a>
                    ) : (
                      <small>{source.source_type || "知识库"}</small>
                    )}
                  </div>
                ))}
              </div>
            </section>
          ) : null}
          {(report.sections || []).map((section) => (
            <section key={section.id || section.title}>
              <h3>{section.title}</h3>
              <p>{section.content}</p>
            </section>
          ))}
          {knowledgeEvidence.length ? (
            <section>
              <h3>RAG 知识证据</h3>
              {knowledgeEvidence.map((item) => (
                <p className="evidence-line" key={item.id}>
                  <strong>{item.source_label || item.id}</strong>：{item.quote}
                  {item.source_url ? (
                    <>
                      {" "}
                      <a href={item.source_url} rel="noreferrer" target="_blank">
                        来源
                      </a>
                    </>
                  ) : null}
                </p>
              ))}
            </section>
          ) : null}
          <section>
            <h3>证据清单</h3>
            {documentEvidence.length === 0 ? <p>暂无文档或指标证据项。</p> : null}
            {documentEvidence.map((item) => (
              <p className="evidence-line" key={item.id}>
                <strong>{item.id}</strong>：{item.quote}
              </p>
            ))}
          </section>
        </div>
      </article>
    </div>
  );
}

function InsightModule({ documents, loadingDocuments }) {
  const [selected, setSelected] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages]);

  function toggleDoc(versionId) {
    setSelected((items) => (items.includes(versionId) ? items.filter((id) => id !== versionId) : [...items, versionId]));
  }

  async function sendMessage() {
    if (!prompt.trim()) {
      setError("请输入分析需求。");
      return;
    }
    if (!sessionId && selected.length === 0) {
      setError("请至少选择一份文档。");
      return;
    }

    const userText = prompt.trim();
    setPrompt("");
    setError("");
    setBusy(true);
    const assistantId = `assistant-${Date.now()}`;
    setMessages((items) => [
      ...items,
      { id: `user-${Date.now()}`, role: "user", content: userText },
      { id: assistantId, role: "assistant", content: "", isStreaming: true },
    ]);

    try {
      const handlers = {
        onMeta: (event) => {
          if (event.session_id) setSessionId(event.session_id);
        },
        onDelta: (chunk) => {
          setMessages((items) =>
            items.map((item) => (item.id === assistantId ? { ...item, content: item.content + chunk } : item)),
          );
        },
        onDone: (event) => {
          if (event.session_id) setSessionId(event.session_id);
        },
      };

      if (sessionId) {
        await api.insight.sendMessageStream(sessionId, userText, handlers);
      } else {
        await api.insight.startSessionStream(selected, userText, handlers);
      }
      setMessages((items) => items.map((item) => (item.id === assistantId ? { ...item, isStreaming: false } : item)));
    } catch (err) {
      setError(err.message || "智能洞察失败");
      setMessages((items) =>
        items.map((item) =>
          item.id === assistantId ? { ...item, content: item.content || "智能洞察失败。", isStreaming: false } : item,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="insight-layout">
      <section className="panel source-panel">
        <h3>数据源</h3>
        <p className="muted">选择文档作为智能洞察上下文。</p>
        <div className="source-list">
          {loadingDocuments ? <p className="empty">加载文档中...</p> : null}
          {!loadingDocuments && documents.length === 0 ? <p className="empty">暂无可分析文档。</p> : null}
          {documents.map((doc) => {
            const versionId = doc.current_version_id;
            return (
              <label className="source-item" key={doc.id}>
                <input
                  checked={selected.includes(versionId)}
                  disabled={busy || !versionId}
                  type="checkbox"
                  onChange={() => toggleDoc(versionId)}
                />
                <span>
                  <strong>{documentTitle(doc)}</strong>
                  <small>{categoryLabel(doc.document_category)}</small>
                  <small>版本 ID：{versionId || "--"}</small>
                </span>
              </label>
            );
          })}
        </div>
      </section>

      <section className="panel chat-panel">
        <div className="section-toolbar">
          <div>
            <h3>{sessionId ? `会话 #${sessionId}` : "新的智能洞察"}</h3>
            <p className="muted">{sessionId ? "继续追问当前会话" : `待发起 | 已选择 ${selected.length} 份文档`}</p>
          </div>
          <Bot size={18} />
        </div>
        <div className="chat-window" ref={listRef}>
          {messages.length === 0 ? (
            <div className="chat-empty">
              <Sparkles size={26} />
              <span>选择文档并发起第一轮分析</span>
            </div>
          ) : (
            messages.map((message) => (
              <div className={`message-row ${message.role}`} key={message.id}>
                <div className="message-bubble">
                  {message.content}
                  {message.isStreaming ? <i /> : null}
                </div>
              </div>
            ))
          )}
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        <div className="chat-input">
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder={sessionId ? "继续追问，例如：先复查什么？" : "输入首轮分析需求，例如：请告诉我现在最需要关注什么。"}
          />
          <button className="primary-button compact" disabled={busy} onClick={sendMessage} type="button">
            <Send size={15} />
            {busy ? "生成中" : sessionId ? "继续追问" : "发起洞察"}
          </button>
        </div>
      </section>
    </div>
  );
}

function RagKnowledgeModule() {
  const [sources, setSources] = useState([]);
  const [results, setResults] = useState([]);
  const [query, setQuery] = useState("空腹血糖 ALT LDL-C 审计复核");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api.knowledge
      .sources()
      .then((items) => {
        if (!cancelled) setSources(items || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "加载 RAG 来源失败");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function searchKnowledge() {
    if (!query.trim()) {
      setError("请输入检索问题。");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const items = await api.knowledge.search({ query: query.trim(), top_k: 8 });
      setResults(items || []);
    } catch (err) {
      setError(err.message || "RAG 检索失败");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  const msdCount = sources.filter((item) => item.source_name === "默沙东诊疗手册大众版").length;
  const chunkCount = sources.reduce((sum, item) => sum + (item.chunk_count || 0), 0);

  return (
    <div className="rag-layout">
      <section className="panel rag-search-panel">
        <div className="section-toolbar">
          <div>
            <h3>RAG 知识检索</h3>
            <p className="muted">BM25 + 关键词 + 医疗同义词混合检索，结果用于 LangGraph 审计报告。</p>
          </div>
          <Database size={18} />
        </div>
        <div className="rag-query-box">
          <textarea value={query} onChange={(event) => setQuery(event.target.value)} />
          <button className="primary-button compact" disabled={loading} onClick={searchKnowledge} type="button">
            <Search size={15} />
            {loading ? "检索中" : "检索知识库"}
          </button>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        <div className="rag-results">
          {results.length === 0 ? <p className="empty">输入问题后查看相关知识、来源和匹配依据。</p> : null}
          {results.map((item) => (
            <article className="rag-result-card" key={`${item.id}-${item.section_title}`}>
              <div>
                <span>{item.source_title}</span>
                <strong>{item.section_title}</strong>
              </div>
              <p>{item.content}</p>
              <div className="rag-score-row">
                <span>总分 {item.score}</span>
                <span>BM25 {item.score_breakdown?.bm25 ?? "--"}</span>
                <span>关键词 {item.score_breakdown?.keyword ?? "--"}</span>
                <span>同义词 {item.score_breakdown?.synonym ?? "--"}</span>
              </div>
              <div className="rag-tags">
                {(item.matched_terms || []).slice(0, 8).map((term) => (
                  <em key={term}>{term}</em>
                ))}
              </div>
              {item.metadata_json?.source_url ? (
                <a href={item.metadata_json.source_url} rel="noreferrer" target="_blank">
                  打开来源
                </a>
              ) : null}
            </article>
          ))}
        </div>
      </section>

      <section className="panel rag-source-side">
        <h3>知识库来源</h3>
        <div className="rag-kpi-grid">
          <span>
            <strong>{sources.length}</strong>
            来源
          </span>
          <span>
            <strong>{chunkCount}</strong>
            知识块
          </span>
          <span>
            <strong>{msdCount}</strong>
            默沙东来源
          </span>
        </div>
        <div className="rag-source-stack">
          {sources.map((source) => (
            <article key={`${source.source_name}-${source.source_url || source.source_title}`}>
              <span>{source.source_type}</span>
              <strong>{source.source_name}</strong>
              <small>{source.sections?.join(" / ")}</small>
              {source.source_url ? (
                <a href={source.source_url} rel="noreferrer" target="_blank">
                  来源页面
                </a>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function MetricsModule() {
  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [fuzzy, setFuzzy] = useState(false);
  const [measurements, setMeasurements] = useState([]);
  const [activeName, setActiveName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const groups = useMemo(() => {
    const map = new Map();
    measurements.forEach((item) => {
      const existing = map.get(item.name) || { name: item.name, unit: item.unit || "--", count: 0 };
      existing.count += 1;
      map.set(item.name, existing);
    });
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
  }, [measurements]);

  const activeRows = useMemo(
    () => measurements.filter((item) => item.name === activeName).sort((a, b) => new Date(a.created_at) - new Date(b.created_at)),
    [activeName, measurements],
  );

  async function searchMeasurements() {
    if (!name.trim()) {
      setError("请输入指标名称。");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await api.measurements.search({
        name: name.trim(),
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        page: 1,
        page_size: 100,
      });
      const rows = response.items || [];
      const filtered = fuzzy ? rows : rows.filter((item) => item.name.trim().toLowerCase() === name.trim().toLowerCase());
      setMeasurements(filtered);
      const names = Array.from(new Set(filtered.map((item) => item.name)));
      setActiveName(names.length === 1 ? names[0] : "");
      if (filtered.length === 0) setError(fuzzy ? "没有找到匹配的指标。" : "没有找到精确匹配的指标。");
    } catch (err) {
      setMeasurements([]);
      setActiveName("");
      setError(err.message || "获取测量数据失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="metrics-layout">
      <section className="panel full">
        <div className="metric-search">
          <label className="field">
            <span>指标名称</span>
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：glucose 或 葡萄糖" />
          </label>
          <label className="field">
            <span>开始时间</span>
            <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          </label>
          <label className="field">
            <span>结束时间</span>
            <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          </label>
          <label className="check-field">
            <input checked={fuzzy} type="checkbox" onChange={(event) => setFuzzy(event.target.checked)} />
            开启模糊搜索
          </label>
          <button className="primary-button compact" disabled={loading} onClick={searchMeasurements} type="button">
            <Search size={15} />
            {loading ? "查询中..." : "查询指标"}
          </button>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
      </section>

      <section className="metric-results">
        <aside className="panel">
          <h3>搜索结果</h3>
          <p className="muted">选择一个指标用于绘图和查看明细。</p>
          <div className="source-list">
            {groups.length === 0 ? <p className="empty">暂无可选指标。</p> : null}
            {groups.map((group) => (
              <button
                className={classNames("metric-choice", activeName === group.name && "active")}
                key={group.name}
                onClick={() => setActiveName(group.name)}
                type="button"
              >
                <span>{group.name}</span>
                <small>
                  {group.count} 条 / {group.unit}
                </small>
              </button>
            ))}
          </div>
        </aside>

        <section className="panel chart-panel">
          <h3>{activeName || "指标趋势"}</h3>
          <SimpleChart rows={activeRows} />
        </section>
      </section>

      <section className="panel full">
        <div className="table-head">
          <span>指标</span>
          <span>数值</span>
          <span>单位</span>
          <span>报告时间</span>
        </div>
        <div className="table-body">
          {activeRows.length === 0 ? <p className="empty">请选择一个指标查看明细。</p> : null}
          {activeRows
            .slice()
            .reverse()
            .map((row) => (
              <div className="table-row" key={row.id}>
                <span>{row.name}</span>
                <span>{row.value_numeric ?? row.value_text}</span>
                <span>{row.unit || "--"}</span>
                <span>{formatDate(row.observed_at || row.created_at)}</span>
              </div>
            ))}
        </div>
      </section>
    </div>
  );
}

function SimpleChart({ rows }) {
  const numericRows = rows.filter((item) => typeof item.value_numeric === "number");
  if (!numericRows.length) {
    return <div className="chart-empty">暂无可展示的图表数据。</div>;
  }

  const width = 680;
  const height = 220;
  const pad = 26;
  const values = numericRows.map((item) => item.value_numeric);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = max - min || 1;
  const points = numericRows.map((item, index) => {
    const x = pad + (index / Math.max(1, numericRows.length - 1)) * (width - pad * 2);
    const y = height - pad - ((item.value_numeric - min) / spread) * (height - pad * 2);
    return { x, y, item };
  });
  const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");

  return (
    <svg className="simple-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="指标趋势图">
      <defs>
        <linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="rgba(24,24,27,0.12)" />
          <stop offset="100%" stopColor="rgba(24,24,27,0)" />
        </linearGradient>
      </defs>
      {[0, 1, 2, 3].map((line) => (
        <line
          key={line}
          stroke="#f4f4f5"
          strokeDasharray="5 5"
          x1={pad}
          x2={width - pad}
          y1={pad + line * ((height - pad * 2) / 3)}
          y2={pad + line * ((height - pad * 2) / 3)}
        />
      ))}
      <path d={`${path} L ${width - pad} ${height - pad} L ${pad} ${height - pad} Z`} fill="url(#chartFill)" />
      <path d={path} fill="none" stroke="#18181b" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
      {points.map((point) => (
        <circle cx={point.x} cy={point.y} fill="#fff" key={point.item.id} r="4" stroke="#18181b" strokeWidth="2" />
      ))}
      <text fill="#71717a" fontSize="11" x={pad} y={height - 4}>
        {formatDate(numericRows[0]?.observed_at || numericRows[0]?.created_at)}
      </text>
      <text fill="#71717a" fontSize="11" textAnchor="end" x={width - pad} y={height - 4}>
        {formatDate(numericRows[numericRows.length - 1]?.observed_at || numericRows[numericRows.length - 1]?.created_at)}
      </text>
    </svg>
  );
}
