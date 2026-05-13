from __future__ import annotations

import json
import re
import ssl
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "thesis_references"
FILES_DIR = OUT_DIR / "files"


@dataclass
class ReferenceSource:
    number: int
    short_name: str
    citation: str
    source_url: str
    download_urls: list[str]
    note: str = ""


REFERENCES: list[ReferenceSource] = [
    ReferenceSource(
        1,
        "nhc_hospital_informatization_standard",
        "国家卫生健康委员会规划与信息司. 全国医院信息化建设标准与规范（试行）[S/OL]. 2018[2026-05-07].",
        "https://www.nhc.gov.cn/ewebeditor/uploadfile/2018/04/20180413162542120.pdf",
        ["https://www.nhc.gov.cn/ewebeditor/uploadfile/2018/04/20180413162542120.pdf"],
    ),
    ReferenceSource(
        2,
        "emr_grade_evaluation_notice",
        "国家卫生健康委办公厅. 关于印发电子病历系统应用水平分级评价管理办法（试行）及评价标准（试行）的通知: 国卫办医函〔2018〕1079号[Z/OL]. 2018.",
        "https://www.nhc.gov.cn/yzygj/c100068/201812/b01f63185ef74a41afa30adeb5c58ccf.shtml",
        ["https://www.nhc.gov.cn/yzygj/c100068/201812/b01f63185ef74a41afa30adeb5c58ccf.shtml"],
    ),
    ReferenceSource(
        3,
        "gbt_35273_personal_information",
        "国家市场监督管理总局, 国家标准化管理委员会. 信息安全技术 个人信息安全规范: GB/T 35273-2020[S]. 北京: 中国标准出版社, 2020.",
        "https://www.antpedia.com/standard/2067794251-1.html",
        ["https://www.antpedia.com/standard/2067794251-1.html"],
        "国家标准全文通常受平台访问限制，保存公开标准信息页用于核验。",
    ),
    ReferenceSource(
        4,
        "emr_text_mining_review",
        "吴宗友, 白昆龙, 杨林蕊, 等. 电子病历文本挖掘研究综述[J]. 计算机研究与发展, 2021,58(3):513-527.",
        "https://crad.ict.ac.cn/fileJSJYJYFZ/journal/article/jsjyjyfz/HTML/2021-03-513.shtml",
        [
            "https://crad.ict.ac.cn/cn/article/pdf/preview/10.7544/issn1000-1239.2021.20200402.pdf",
            "https://crad.ict.ac.cn/fileJSJYJYFZ/journal/article/jsjyjyfz/HTML/2021-03-513.shtml",
        ],
    ),
    ReferenceSource(
        5,
        "chinese_emr_ner_progress",
        "杜晋华, 尹浩, 冯嵩. 中文电子病历命名实体识别的研究与进展[J]. 电子学报, 2022,50(12):3030-3053.",
        "https://www.ejournal.org.cn/CN/abstract/article/0372-2112/13029",
        [
            "https://www.ejournal.org.cn/CN/article/downloadArticleFile.do?attachType=PDF&id=13029",
            "https://www.ejournal.org.cn/CN/abstract/article/0372-2112/13029",
        ],
        "电子学报站点对本机脚本访问返回 403 时，保留官方条目 URL 和下载失败记录。",
    ),
    ReferenceSource(
        6,
        "emr_ner_multifeature",
        "韩普, 刘亦卓, 李晓艳. 基于深度学习和多特征融合的中文电子病历实体识别研究[J]. 南京大学学报(自然科学), 2019,55(6):942-951.",
        "https://jns.nju.edu.cn/CN/abstract/article/0469-5097/1157",
        [
            "https://jns.nju.edu.cn/CN/article/downloadArticleFile.do?attachType=PDF&id=1157",
            "https://jns.nju.edu.cn/CN/abstract/article/0469-5097/1157",
        ],
    ),
    ReferenceSource(
        7,
        "emr_ner_semantic_boundary",
        "崔少国, 陈俊桦, 李晓虹. 融合语义及边界信息的中文电子病历命名实体识别[J]. 电子科技大学学报, 2022,51(4):565-571.",
        "https://www.juestc.uestc.edu.cn/article/doi/10.12178/1001-0548.2021350",
        [
            "https://www.juestc.uestc.edu.cn/cn/article/pdf/preview/10.12178/1001-0548.2021350.pdf",
            "https://www.juestc.uestc.edu.cn/article/doi/10.12178/1001-0548.2021350",
        ],
    ),
    ReferenceSource(
        8,
        "real_world_emr_data_governance",
        "盖彦蓉, 张云秋, 张慧, 等. 面向知识抽取的真实世界中文电子病历数据质量分析与治理对策研究[J]. 医学信息学杂志, 2025,46(12):47-53.",
        "https://www.yxxxx.ac.cn/yxxxx/article/html/20251208",
        ["https://www.yxxxx.ac.cn/yxxxx/article/html/20251208"],
    ),
    ReferenceSource(
        9,
        "medical_glm_opportunities_challenges",
        "肖仰华, 徐一丹. 大规模生成式语言模型在医疗领域的应用: 机遇与挑战[J]. 医学信息学杂志, 2023,44(9):1-11.",
        "https://www.yxxxx.ac.cn/yxxxx/article/abstract/20230901",
        [
            "https://www.yxxxx.ac.cn/yxxxx/article/pdf/20230901",
            "https://www.yxxxx.ac.cn/yxxxx/article/html/20230901",
            "https://www.yxxxx.ac.cn/yxxxx/article/abstract/20230901",
        ],
    ),
    ReferenceSource(
        10,
        "knowledge_enhanced_medical_lm",
        "康砚澜, 郭倩宇, 张文强, 等. 基于知识增强的医学语言模型: 现状、技术与应用[J]. 医学信息学杂志, 2023,44(9):12-22.",
        "https://www.yxxxx.ac.cn/yxxxx/article/abstract/20230902",
        [
            "https://www.yxxxx.ac.cn/yxxxx/article/pdf/20230902",
            "https://www.yxxxx.ac.cn/yxxxx/article/html/20230902",
            "https://www.yxxxx.ac.cn/yxxxx/article/abstract/20230902",
        ],
    ),
    ReferenceSource(
        11,
        "generative_llm_medical_applications",
        "颜见智, 何雨鑫, 骆子烨, 等. 生成式大语言模型在医疗领域的潜在典型应用与面临的挑战[J]. 医学信息学杂志, 2023,44(9):23-31.",
        "https://www.yxxxx.ac.cn/yxxxx/article/abstract/20230903",
        [
            "https://www.yxxxx.ac.cn/yxxxx/article/pdf/20230903",
            "https://www.yxxxx.ac.cn/yxxxx/article/html/20230903",
            "https://www.yxxxx.ac.cn/yxxxx/article/abstract/20230903",
        ],
    ),
    ReferenceSource(
        12,
        "medical_foundation_model",
        "陈晓红, 刘浏, 袁依格, 等. 医疗大模型技术及应用发展研究[J]. 中国工程科学, 2024,26(6):77-88.",
        "https://www.engineering.org.cn/sscae/CN/1160105942421398316",
        [
            "https://www.engineering.org.cn/sscae/CN/PDF/10.15302/J-SSCAE-2024.07.020",
            "https://www.engineering.org.cn/sscae/CN/1160105942421398316",
        ],
    ),
    ReferenceSource(
        13,
        "medical_llm_frontier_applications",
        "何剑虎, 王德健, 赵志锐, 等. 大语言模型在医疗领域的前沿研究与创新应用[J]. 医学信息学杂志, 2024,45(9):10-18.",
        "https://www.yxxxx.ac.cn/yxxxx/article/abstract/20240902",
        [
            "https://www.yxxxx.ac.cn/yxxxx/article/pdf/20240902",
            "https://www.yxxxx.ac.cn/yxxxx/article/html/20240902",
            "https://www.yxxxx.ac.cn/yxxxx/article/abstract/20240902",
        ],
    ),
    ReferenceSource(
        14,
        "software_engineering_intro",
        "张海藩, 牟永敏. 软件工程导论[M]. 6版. 北京: 清华大学出版社, 2013.",
        "https://www.tup.com.cn/bookscenter/book_05016406.html",
        ["https://www.tup.com.cn/bookscenter/book_05016406.html"],
        "教材版权受保护，保存出版社图书详情页用于核验。",
    ),
    ReferenceSource(
        15,
        "database_system_concepts_cn",
        "王珊, 萨师煊. 数据库系统概论[M]. 5版. 北京: 高等教育出版社, 2014.",
        "https://xuanshu.hep.com.cn/front/book/findBookDetails?bookId=5ad8da07f18f967ee7f36d46",
        ["https://xuanshu.hep.com.cn/front/book/findBookDetails?bookId=5ad8da07f18f967ee7f36d46"],
        "教材版权受保护，保存出版社图书详情页用于核验。",
    ),
    ReferenceSource(
        16,
        "statistical_nlp_cn",
        "宗成庆. 统计自然语言处理[M]. 2版. 北京: 清华大学出版社, 2013.",
        "https://www.tup.com.cn/bookscenter/book_03911901.html",
        ["https://www.tup.com.cn/bookscenter/book_03911901.html"],
        "教材版权受保护，保存出版社图书详情页用于核验；若出版社旧页面不可用则记录失败。",
    ),
    ReferenceSource(
        17,
        "machine_learning_zhou",
        "周志华. 机器学习[M]. 北京: 清华大学出版社, 2016.",
        "https://www.tup.tsinghua.edu.cn/bookscenter/book_06402703.html",
        ["https://www.tup.tsinghua.edu.cn/bookscenter/book_06402703.html"],
        "教材版权受保护，保存出版社图书详情页用于核验。",
    ),
    ReferenceSource(
        18,
        "nndl_qiu",
        "邱锡鹏. 神经网络与深度学习[M]. 北京: 机械工业出版社, 2020.",
        "https://nndl.github.io/",
        ["https://nndl.github.io/"],
        "作者公开主页提供引用信息；不下载盗版教材全文。",
    ),
    ReferenceSource(
        19,
        "rag_neurips",
        "Lewis P, Perez E, Piktus A, et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks[C]//Advances in Neural Information Processing Systems. 2020,33:9459-9474.",
        "https://arxiv.org/abs/2005.11401",
        ["https://arxiv.org/pdf/2005.11401", "https://arxiv.org/abs/2005.11401"],
    ),
    ReferenceSource(
        20,
        "react_iclr",
        "Yao S, Zhao J, Yu D, et al. ReAct: Synergizing Reasoning and Acting in Language Models[C]//International Conference on Learning Representations. 2023.",
        "https://arxiv.org/abs/2210.03629",
        ["https://arxiv.org/pdf/2210.03629", "https://arxiv.org/abs/2210.03629"],
    ),
    ReferenceSource(
        21,
        "autogen_arxiv",
        "Wu Q, Bansal G, Zhang J, et al. AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation[EB/OL]. arXiv:2308.08155, 2023[2026-05-07].",
        "https://arxiv.org/abs/2308.08155",
        ["https://arxiv.org/pdf/2308.08155", "https://arxiv.org/abs/2308.08155"],
    ),
    ReferenceSource(
        22,
        "langgraph_overview",
        "LangChain. LangGraph overview[EB/OL]. [2026-05-07]. https://docs.langchain.com/oss/python/langgraph/overview",
        "https://docs.langchain.com/oss/python/langgraph/overview",
        ["https://docs.langchain.com/oss/python/langgraph/overview"],
    ),
]


def safe_fetch(url: str) -> tuple[bytes, str]:
    parts = urlsplit(url)
    url = urlunsplit((parts.scheme, parts.netloc, quote(parts.path), parts.query, parts.fragment))
    context = ssl._create_unverified_context()
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/html,application/pdf,application/xhtml+xml,*/*",
        },
    )
    with urlopen(req, timeout=12, context=context) as response:
        content_type = response.headers.get("Content-Type", "")
        return response.read(), content_type


def extension_for(url: str, content_type: str, data: bytes) -> str:
    lowered = content_type.lower()
    if "pdf" in lowered or data[:4] == b"%PDF":
        return ".pdf"
    if "xml" in lowered or url.lower().endswith(".xml"):
        return ".xml"
    return ".html"


def discover_pdf_links(base_url: str, html: bytes) -> list[str]:
    text = html.decode("utf-8", errors="ignore")
    links: list[str] = []
    for href in re.findall(r'href=["\']([^"\']+)["\']', text, flags=re.I):
        if "pdf" in href.lower() or "/article/pdf/" in href:
            links.append(urljoin(base_url, href))
    return links


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for ref in REFERENCES:
        record = asdict(ref)
        record["downloaded_files"] = []
        record["errors"] = []
        for existing in sorted(FILES_DIR.glob(f"{ref.number:02d}_{ref.short_name}.*")):
            record["downloaded_files"].append(
                {
                    "url": "local-existing-file",
                    "file": str(existing.relative_to(OUT_DIR)).replace("\\", "/"),
                    "content_type": "existing/local",
                    "bytes": existing.stat().st_size,
                }
            )
        seen_urls: set[str] = set()
        queue = list(ref.download_urls)

        for url in queue:
            has_pdf = any(item["file"].lower().endswith(".pdf") for item in record["downloaded_files"])
            has_html = any(item["file"].lower().endswith(".html") for item in record["downloaded_files"])
            if has_pdf or (has_html and not any("pdf" in candidate.lower() for candidate in queue)):
                break
            if url in seen_urls:
                continue
            seen_urls.add(url)
            try:
                data, content_type = safe_fetch(url)
                ext = extension_for(url, content_type, data)
                filename = f"{ref.number:02d}_{ref.short_name}{ext}"
                path = FILES_DIR / filename
                if path.exists() and path.read_bytes() == data:
                    pass
                else:
                    path.write_bytes(data)
                record["downloaded_files"].append(
                    {
                        "url": url,
                        "file": str(path.relative_to(OUT_DIR)).replace("\\", "/"),
                        "content_type": content_type,
                        "bytes": len(data),
                    }
                )
                if ext == ".html":
                    for discovered in discover_pdf_links(url, data):
                        if discovered not in seen_urls and discovered not in queue:
                            queue.append(discovered)
                if ext == ".pdf":
                    break
            except HTTPError as exc:
                record["errors"].append({"url": url, "error": f"HTTP {exc.code}: {exc.reason}"})
            except (URLError, TimeoutError, OSError, ValueError) as exc:
                record["errors"].append({"url": url, "error": repr(exc)})
            time.sleep(0.2)

        results.append(record)

    manifest = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "policy": "Only public official/open-access pages or PDFs were downloaded. Copyrighted textbooks and paywalled standards are represented by publisher/official metadata pages.",
        "references": results,
    }
    (OUT_DIR / "references_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Thesis References",
        "",
        "本目录保存论文参考文献的公开原文、官方页面或核验页面。",
        "教材、标准等受版权保护的资料不从非授权站点下载全文，只保存出版社或公开标准信息页。",
        "",
    ]
    for ref in results:
        status = "已下载" if ref["downloaded_files"] else "未下载"
        lines.append(f"## [{ref['number']}] {ref['short_name']} - {status}")
        lines.append(ref["citation"])
        lines.append(f"Source: {ref['source_url']}")
        if ref["note"]:
            lines.append(f"Note: {ref['note']}")
        for item in ref["downloaded_files"]:
            lines.append(f"- {item['file']} ({item['bytes']} bytes)")
        for item in ref["errors"]:
            lines.append(f"- ERROR {item['url']}: {item['error']}")
        lines.append("")
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")

    total_files = sum(len(item["downloaded_files"]) for item in results)
    failed = [item for item in results if not item["downloaded_files"]]
    print(f"references={len(results)} downloaded_files={total_files} failed_refs={len(failed)}")
    if failed:
        print("failed:", ", ".join(f"{item['number']:02d}" for item in failed))


if __name__ == "__main__":
    main()
