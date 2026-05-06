const API_BASE = "/api";

let authToken = localStorage.getItem("token");
let unauthorizedHandler = null;

function toQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.append(key, String(value));
    }
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

async function parseError(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (response.status === 401 && typeof unauthorizedHandler === "function") {
    unauthorizedHandler();
  }

  const message =
    payload?.error?.message ||
    payload?.detail?.message ||
    (Array.isArray(payload?.detail) ? payload.detail.map((item) => item.msg).join(", ") : payload?.detail) ||
    payload?.message ||
    `请求失败，状态码 ${response.status}`;
  const error = new Error(message);
  error.status = response.status;
  error.payload = payload;
  throw error;
}

async function request(path, options = {}) {
  const {
    method = "GET",
    params,
    body,
    headers = {},
    token = authToken,
    isFormData = false,
  } = options;

  const response = await fetch(`${API_BASE}${path}${toQuery(params)}`, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...headers,
    },
    body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
  });

  if (!response.ok) {
    await parseError(response);
  }
  return response.status === 204 ? null : response.json();
}

async function readNdjsonStream(path, body, handlers = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal: handlers.signal,
  });

  if (!response.ok) {
    await parseError(response);
  }
  if (!response.body) {
    throw new Error("流式响应不可用");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let donePayload = null;

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      let event;
      try {
        event = JSON.parse(trimmed);
      } catch {
        continue;
      }
      if (event.type === "meta") handlers.onMeta?.(event);
      if (event.type === "delta") handlers.onDelta?.(event.content || "");
      if (event.type === "error") throw new Error(event.message || "流式洞察失败");
      if (event.type === "done") {
        donePayload = event;
        handlers.onDone?.(event);
      }
    }
  }

  if (buffer.trim()) {
    const event = JSON.parse(buffer.trim());
    if (event.type === "done") {
      donePayload = event;
      handlers.onDone?.(event);
    }
  }
  return donePayload;
}

export function setToken(token) {
  authToken = token || null;
  if (authToken) localStorage.setItem("token", authToken);
  else localStorage.removeItem("token");
}

export function getToken() {
  return authToken;
}

export function onUnauthorized(handler) {
  unauthorizedHandler = handler;
}

export const api = {
  setToken,
  getToken,
  onUnauthorized,
  auth: {
    register(email, password) {
      return request("/auth/register", { method: "POST", token: null, body: { email, password } });
    },
    login(email, password) {
      return request("/auth/login", { method: "POST", token: null, body: { email, password } });
    },
    me() {
      return request("/auth/me");
    },
  },
  files: {
    upload(file, displayName) {
      const form = new FormData();
      form.append("file", file);
      form.append("display_name", displayName);
      return request("/files/upload", { method: "POST", body: form, isFormData: true });
    },
  },
  ocr: {
    extract(recordFileId, params = {}) {
      return request(`/ocr/files/${recordFileId}/extract`, {
        method: "POST",
        params: { sync: true, ...params },
      });
    },
    getRevision(ocrResultId) {
      return request(`/ocr/revisions/${ocrResultId}`);
    },
  },
  ingestion: {
    normalize(ocrResultId, params = {}) {
      return request(`/ingestion/ocr-results/${ocrResultId}/normalize`, {
        method: "POST",
        params: { sync: true, ...params },
      });
    },
  },
  documents: {
    list(params = {}) {
      return request("/documents", { params });
    },
    getById(id) {
      return request(`/documents/${id}`);
    },
    rename(id, newName) {
      return request(`/documents/${id}/rename`, { method: "PATCH", params: { new_name: newName } });
    },
    remove(id) {
      return request(`/documents/${id}`, { method: "DELETE" });
    },
  },
  tasks: {
    list(params = {}) {
      return request("/tasks", { params });
    },
    getStatus(id) {
      return request(`/tasks/${id}`);
    },
    getResult(id) {
      return request(`/tasks/${id}/result`);
    },
  },
  measurements: {
    list(params = {}) {
      return request("/measurements", { params });
    },
    search(params = {}) {
      return request("/measurements/search", { params });
    },
    timeseries(params = {}) {
      return request("/measurements/timeseries", { params });
    },
  },
  insight: {
    listSessions() {
      return request("/insight/sessions");
    },
    getSession(id) {
      return request(`/insight/sessions/${id}`);
    },
    listMessages(id) {
      return request(`/insight/sessions/${id}/messages`);
    },
    deleteSession(id) {
      return request(`/insight/sessions/${id}`, { method: "DELETE" });
    },
    startSessionStream(documentVersionIds, prompt, handlers = {}) {
      return readNdjsonStream(
        "/insight/sessions/stream",
        { selected_document_version_ids: documentVersionIds, prompt },
        handlers,
      );
    },
    sendMessageStream(sessionId, message, handlers = {}) {
      return readNdjsonStream(`/insight/sessions/${sessionId}/messages/stream`, { message }, handlers);
    },
  },
  auditReports: {
    create(documentVersionIds, title = "综合审计报告") {
      return request("/audit-reports", {
        method: "POST",
        body: {
          selected_document_version_ids: documentVersionIds,
          title,
          max_iterations: 8,
        },
      });
    },
    list() {
      return request("/audit-reports");
    },
    get(id) {
      return request(`/audit-reports/${id}`);
    },
    events(id) {
      return request(`/audit-reports/${id}/events`);
    },
  },
  health: {
    check() {
      return request("/health", { token: null });
    },
  },
};
