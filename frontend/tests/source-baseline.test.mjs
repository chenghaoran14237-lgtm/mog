import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const read = (path) => readFileSync(join(root, path), "utf8");

describe("React source baseline", () => {
  it("keeps a maintainable React frontend source tree", () => {
    for (const path of [
      "package.json",
      "index.html",
      "src/main.jsx",
      "src/App.jsx",
      "src/services/api.js",
      "src/index.css",
    ]) {
      assert.equal(existsSync(join(root, path)), true, `${path} should exist`);
    }
  });

  it("preserves current HealthDoc OS user-facing modules", () => {
    const app = read("src/App.jsx");
    for (const text of [
      "HealthDoc.OS",
      "文档接入流程",
      "文档库",
      "综合审计报告",
      "智能洞察",
      "RAG 知识库",
      "指标探索",
      "OCR 提取",
      "结构化标准化",
    ]) {
      assert.match(app, new RegExp(text.replace(".", "\\.")));
    }
  });

  it("keeps API calls aligned with the current backend", () => {
    const api = read("src/services/api.js");
    for (const endpoint of [
      "/auth/login",
      "/auth/me",
      "/files/upload",
      "/ocr/files/",
      "/ingestion/ocr-results/",
      "/documents",
      "/measurements/search",
      "/insight/sessions/stream",
      "/audit-reports",
      "/knowledge/search",
      "/knowledge/sources",
    ]) {
      assert.match(api, new RegExp(endpoint.replaceAll("/", "\\/")));
    }
  });
});
