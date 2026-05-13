# 文档索引

本目录按用途分为产品/项目文档、毕业论文材料、历史归档和私有材料四类。新增文件时优先放入对应目录，避免再把论文过程文件、个人材料和项目说明混在 `docs/` 根目录。

## 目录约定

- `product/`：项目相关文档、API 测试报告、前端原型和视觉基线。
- `thesis/`：毕业论文正文、开题报告、学校模板、参考文献、论文图表和最终渲染检查产物。
- `archive/`：已经完成或被替代的实现计划、旧原型、旧渲染轮次和重复产物。
- `private/`：个人简历、联系方式材料、疑似版权全文等不适合提交到公开仓库的文件；该目录已加入 `.gitignore`。

## 项目文档

- `product/api-smoke/2026-04-29.md`：2026-04-29 API 全流程 smoke test 历史报告。
- `product/prototypes/`：综合审计报告页面的 HTML 原型和备份原型。
- `product/style-baseline/`：2026-04-29 前端视觉基线，包括编译后的 HTML/CSS/JS 快照。

## 毕业论文材料

- `thesis/drafts/`：论文正文草稿/定稿 DOCX。
- `thesis/proposal/`：开题报告。
- `thesis/school/`：学院毕业设计规范。
- `thesis/school/templates/`：学校正文、附录、参考文献、插图表公式说明和附件表格模板。
- `thesis/references/`：参考文献清单、下载 manifest 和公开可核验来源文件。
- `thesis/assets/figures/`：论文正文使用的系统架构图、流程图、ER 图、测试图等。
- `thesis/assets/project_snapshot.json`：用于生成论文图表的项目快照数据。
- `thesis/assets/render_check_final/`：最终一轮论文 PDF 渲染和逐页 PNG 检查图。
- `thesis/samples/`：往届论文样例和样例页截图。

## 归档材料

- `archive/plans/2026-05-06-langgraph-audit-report.md`：LangGraph 综合审计报告实现计划，当前已作为历史记录归档。
- `archive/thesis-render-checks/`：旧版论文渲染检查、封面检查和重复 PDF。

## 私有/不公开材料

`private/` 当前用于存放：

- 个人简历 Markdown/PDF。
- 从参考文献包中隔离出来的教材类 PDF 全文。

这些文件仍保留在本地工作区，便于个人使用，但默认不进入 git。

## 维护规则

- 项目运行说明只放在仓库根目录 `README.md` 和 `docs/product/`。
- 毕业论文相关材料统一放 `docs/thesis/`。
- 过程截图、旧版本 PDF、临时 DOCX 放 `docs/archive/`，只保留必要的最终产物在 `docs/thesis/assets/render_check_final/`。
- 含手机号、邮箱、个人简历、非授权全文资料的文件放 `docs/private/`，不要提交到公开仓库。
