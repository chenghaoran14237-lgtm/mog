const fs = require("fs");
const path = require("path");
const PDFDocument = require("pdfkit");

const root = path.resolve(__dirname, "..");
const output = path.join(root, "docs", "resume_chenghaoran_onepage.pdf");
fs.mkdirSync(path.dirname(output), { recursive: true });

const doc = new PDFDocument({
  size: "A4",
  margin: 0,
  bufferPages: false,
  info: {
    Title: "程浩然 - 简历",
    Author: "程浩然",
    Subject: "全栈开发 / 后端开发 / AI 应用开发",
  },
});

doc.pipe(fs.createWriteStream(output));

const fontRegular = "C:/Windows/Fonts/Deng.ttf";
const fontBold = "C:/Windows/Fonts/Dengb.ttf";
doc.registerFont("CN", fontRegular);
doc.registerFont("CN-Bold", fontBold);

const page = {
  w: doc.page.width,
  h: doc.page.height,
};

const colors = {
  ink: "#17212b",
  muted: "#586674",
  light: "#edf3f5",
  line: "#cdd9dd",
  accent: "#0f5d66",
  accentDark: "#0b3d45",
  chip: "#e6f0f2",
};

const margin = 30;
const leftW = 158;
const gap = 18;
const rightX = margin + leftW + gap;
const rightW = page.w - rightX - margin;
const bottomLimit = page.h - 30;

function text(str, x, y, opts = {}) {
  const {
    size = 8.2,
    font = "CN",
    color = colors.ink,
    width,
    lineGap = 1.3,
    align,
    continued,
    link,
  } = opts;
  doc.font(font).fontSize(size).fillColor(color);
  doc.text(str, x, y, {
    width,
    lineGap,
    align,
    continued,
    link,
  });
  return doc.y;
}

function rule(x, y, w, color = colors.line, width = 0.7) {
  doc
    .strokeColor(color)
    .lineWidth(width)
    .moveTo(x, y)
    .lineTo(x + w, y)
    .stroke();
}

function sectionTitle(title, x, y, w) {
  text(title, x, y, {
    size: 10.2,
    font: "CN-Bold",
    color: colors.accentDark,
    width: w,
  });
  rule(x, y + 15.2, w, colors.accent, 1);
  return y + 20.5;
}

function chip(label, x, y, w) {
  doc.roundedRect(x, y, w, 14, 4).fill(colors.chip);
  text(label, x + 5, y + 3.1, {
    size: 6.8,
    font: "CN-Bold",
    color: colors.accentDark,
    width: w - 10,
    align: "center",
  });
}

function bullet(str, x, y, w, opts = {}) {
  const { size = 8.0, gapAfter = 5.1, color = colors.ink } = opts;
  doc.circle(x + 2.3, y + 4.9, 1.25).fill(colors.accent);
  const after = text(str, x + 8, y, {
    size,
    color,
    width: w - 8,
    lineGap: 1.45,
  });
  return after + gapAfter;
}

function compactLine(label, value, x, y, w) {
  text(label, x, y, {
    size: 7.8,
    font: "CN-Bold",
    color: colors.accentDark,
    width: w,
  });
  return text(value, x, y + 11.8, {
    size: 7.55,
    color: colors.ink,
    width: w,
    lineGap: 1.15,
  }) + 6.2;
}

function project(title, meta, bullets, x, y, w, options = {}) {
  const titleSize = options.titleSize || 9.2;
  text(title, x, y, {
    size: titleSize,
    font: "CN-Bold",
    color: colors.ink,
    width: w,
  });
  y += 13;
  text(meta, x, y, {
    size: 7.25,
    color: colors.muted,
    width: w,
    lineGap: 0.85,
  });
  y = doc.y + 4.2;
  for (const item of bullets) {
    y = bullet(item, x, y, w, { size: options.bulletSize || 7.75, gapAfter: options.gapAfter || 4.2 });
  }
  return y + (options.after || 3);
}

// Header
doc.rect(0, 0, page.w, 96).fill("#f7fbfc");
doc.rect(0, 0, 9, page.h).fill(colors.accent);
text("程浩然", margin, 24, {
  size: 22,
  font: "CN-Bold",
  color: colors.accentDark,
  width: 105,
});
text("全栈开发 / 后端开发 / AI 应用开发", margin + 112, 30, {
  size: 10.2,
  font: "CN-Bold",
  color: colors.ink,
  width: 230,
});
text("北京信息科技大学 · 计算机科学与技术 · 2026 年 6 月毕业", margin + 112, 46, {
  size: 8,
  color: colors.muted,
  width: 260,
});
text("15201295998", page.w - margin - 176, 27, {
  size: 8.2,
  font: "CN-Bold",
  color: colors.ink,
  width: 176,
  align: "right",
});
text("chenghaoran14237@gmail.com", page.w - margin - 176, 41, {
  size: 7.4,
  color: colors.muted,
  width: 176,
  align: "right",
});
text("github.com/chenghaoran14237-lgtm", page.w - margin - 176, 54, {
  size: 7.4,
  color: colors.accent,
  width: 176,
  align: "right",
  link: "https://github.com/chenghaoran14237-lgtm",
});

text(
  "具备全栈开发实习经历，做过 AI 导写、运营后台、H5、医疗文档管理与 LangGraph 多 Agent 审计系统；能从数据模型、接口、任务流到前端展示完成闭环落地。",
  margin,
  73,
  {
    size: 8.0,
    color: colors.ink,
    width: page.w - margin * 2,
    lineGap: 1.0,
  },
);

// Left column
let yL = 114;
yL = sectionTitle("教育背景", margin, yL, leftW);
yL = compactLine("北京信息科技大学", "计算机科学与技术 · 本科\n预计 2026 年 6 月毕业", margin, yL, leftW);

yL = sectionTitle("核心技能", margin, yL + 2, leftW);
yL = compactLine("后端", "Python / FastAPI / Flask / SQLAlchemy / Alembic / Pydantic / REST API", margin, yL, leftW);
yL = compactLine("前端", "Vue 3 / React / TypeScript / Vite / Vben Admin / Vant / Element Plus / ECharts", margin, yL, leftW);
yL = compactLine("AI 应用", "LLM API / DeepSeek / OCR / RAG 基础 / Agent / LangGraph / 多 Agent 状态机", margin, yL, leftW);
yL = compactLine("工程化", "MySQL / Docker / Nginx / Git / GitHub / pytest / Mock 数据 / 前后端联调", margin, yL, leftW);

yL = sectionTitle("项目关键词", margin, yL + 2, leftW);
const chips = [
  ["LangGraph", 62],
  ["医疗审计", 62],
  ["LLM 标准化", 74],
  ["任务流", 48],
  ["运营后台", 62],
  ["H5", 34],
  ["OAuth", 48],
  ["Excel Agent", 72],
];
let cx = margin;
let cy = yL;
for (const [label, w] of chips) {
  if (cx + w > margin + leftW) {
    cx = margin;
    cy += 18;
  }
  chip(label, cx, cy, w);
  cx += w + 5;
}
yL = cy + 23;

yL = sectionTitle("开源与学习", margin, yL, leftW);
yL = bullet("GitHub 关注 Agent、RAG、多 Agent、AI 工程化方向项目。", margin, yL, leftW, { size: 7.45, gapAfter: 4.0 });
yL = bullet("公开仓库包含 feihe、mog、DataWhisper、bytebase-login-demo 等项目。", margin, yL, leftW, { size: 7.45, gapAfter: 4.0 });

yL = sectionTitle("个人优势", margin, yL + 2, leftW);
yL = bullet("能独立完成数据模型、接口、任务流、前端展示和测试验证。", margin, yL, leftW, { size: 7.45, gapAfter: 4.0 });
yL = bullet("熟悉从 Mock 数据到真实 API 联调的工程闭环。", margin, yL, leftW, { size: 7.45, gapAfter: 4.0 });
yL = bullet("对 AI 应用工程化、多 Agent 编排和医疗审计场景有持续实践。", margin, yL, leftW, { size: 7.45, gapAfter: 4.0 });

// Right column
let yR = 114;
yR = sectionTitle("实习经历", rightX, yR, rightW);
text("衔远科技｜全栈开发实习生", rightX, yR, {
  size: 9.2,
  font: "CN-Bold",
  color: colors.ink,
  width: rightW,
});
yR = text(
  "参与 AI 应用、运营后台、H5 页面和医疗审计系统开发，承担后端接口、数据模型、前端页面、测试数据和部署联调等工作。",
  rightX,
  yR + 13.5,
  {
    size: 7.8,
    color: colors.muted,
    width: rightW,
    lineGap: 1.05,
  },
) + 7;

yR = project(
  "飞鹤 KOS 智能 AI 笔记导写及管理系统",
  "衔远科技实习项目｜Python 3.13 / Aury Boot / Redis Worker / Vue 3 / Vben Admin / Vant / Docker",
  [
    "参与后端 API、Worker、Admin 管理台、H5 消费端开发，支撑评论任务创建、重试、结果查询、执行历史和运营侧调试。",
    "参与小红书笔记抓取与缓存、知识库匹配、AI 评论生成、第三方回调 outbox、任务恢复和异常重试链路建设。",
    "改造 Admin 页面与 RBAC 联调，覆盖运营总览、评论任务、抓取任务、回传日志、知识库、业务配置和管理账号。",
    "补充测试用例，覆盖回调 outbox、任务恢复、Prompt 配置、结构化调用超时、URL 解析等场景。",
  ],
  rightX,
  yR,
  rightW,
  { bulletSize: 7.75, gapAfter: 4.2, after: 4 },
);

yR = project(
  "基于 LangGraph 的多 Agent 医疗审计系统",
  "衔远科技实习项目 / 毕设方向｜FastAPI / SQLAlchemy / Alembic / LangGraph / DeepSeek / React / MySQL",
  [
    "设计医疗文档处理链路：文件上传、OCR Provider、标准化 Provider、文档版本、结构化指标、任务状态和 Provider 事件记录。",
    "实现 DeepSeek/OpenAI-compatible LLM 标准化与规则兜底，在 LLM 异常时回退抽取，提升入库稳定性。",
    "落地 LangGraph 状态机型多 Agent 审计架构，包含证据抽取、指标一致性、跨文档冲突、风险提示、合规审计、引用校验、安全复核、报告持久化等节点。",
    "实现真实事件流转表和节点状态表，前端通过轮询展示节点高亮、边流转、循环回退和最终综合审计报告。",
    "构造体检/化验/病历 Mock 数据并完成端到端测试：登录、上传、OCR、标准化、入库、指标检索、审计报告生成。",
  ],
  rightX,
  yR,
  rightW,
  { bulletSize: 7.65, gapAfter: 3.8, after: 4 },
);

yR = sectionTitle("个人项目", rightX, yR + 1, rightW);
yR = project(
  "DataWhisper：Excel 数据智能分析 Agent",
  "github.com/chenghaoran14237-lgtm/DataWhisper｜Python / OpenAI API / Vue 3 / Element Plus / ECharts",
  [
    "实现 Excel 上传、字段匹配、缺失值处理、会话管理、摘要触发、趋势分析和多步工具 Agent 测试。",
    "前端使用 Vue 3、Element Plus、ECharts 构建数据分析交互页面和可视化能力。",
  ],
  rightX,
  yR,
  rightW,
  { bulletSize: 7.55, gapAfter: 3.5, after: 3 },
);

yR = project(
  "Bytebase-like Login Demo：第三方登录与用户管理",
  "github.com/chenghaoran14237-lgtm/bytebase-login-demo｜Flask / Supabase Auth / Postgres / GitHub Pages",
  [
    "实现 GitHub / Google OAuth 登录回调、用户 upsert、登录事件记录，以及用户查询、编辑、删除和登录历史接口。",
  ],
  rightX,
  yR,
  rightW,
  { bulletSize: 7.55, gapAfter: 3.2, after: 0 },
);

if (Math.max(yL, yR) > bottomLimit) {
  doc
    .font("CN-Bold")
    .fontSize(8)
    .fillColor("#b42318")
    .text(`警告：内容可能超出页面 y=${Math.max(yL, yR).toFixed(1)}`, margin, bottomLimit - 12);
}

rule(margin, page.h - 24, page.w - margin * 2, "#e0e7ea", 0.5);
text("求职方向：全栈开发 / 后端开发 / AI 应用开发", margin, page.h - 19, {
  size: 6.5,
  color: colors.muted,
  width: page.w - margin * 2,
  align: "center",
});

doc.end();
console.log(output);
