"""四步知识库自动化流水线。

采集 → 分析 → 整理 → 保存
"""

import argparse
import json
import logging
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from model_client import chat_with_retry, create_provider

logger = logging.getLogger(__name__)

RAW_DIR = Path("knowledge/raw")
ARTICLES_DIR = Path("knowledge/articles")
GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
GITHUB_TOKEN = __import__("os").environ.get("GITHUB_TOKEN", "")

RSS_FEEDS: dict[str, str] = {
    "arxiv-cs-ai": "https://export.arxiv.org/rss/cs.AI",
    "arxiv-cs-cl": "https://export.arxiv.org/rss/cs.CL",
    "arxiv-cs-lg": "https://export.arxiv.org/rss/cs.LG",
}

AI_KEYWORDS: list[str] = [
    "ai", "llm", "agent", "大模型", "智能体", "rag",
    "inference", "fine-tuning", "transformer", "embedding",
    "langchain", "openai", "deepseek",
]

TAG_NORMALIZE = re.compile(r"[^a-z0-9-]")


def _slugify(text: str) -> str:
    """将文本转换为 URL 友好的 slug。

    Args:
        text: 原始文本。

    Returns:
        小写连字符 slug。
    """
    text = text.lower().strip()
    text = TAG_NORMALIZE.sub("-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:50]


def _is_ai_related(title: str, description: str = "") -> bool:
    """判断内容是否属于 AI 领域。

    Args:
        title: 标题。
        description: 描述。

    Returns:
        True 表示相关。
    """
    text = f"{title} {description}".lower()
    return any(kw in text for kw in AI_KEYWORDS)


# ═══════════════════════════════════════════
# Step 1: 采集
# ═══════════════════════════════════════════


def collect_github(limit: int = 10) -> list[dict[str, Any]]:
    """从 GitHub Search API 采集 AI 相关仓库。

    Args:
        limit: 最大采集数量。

    Returns:
        标准化条目列表。
    """
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    queries = [
        "ai+in:name,description,topics",
        "llm+in:name,description,topics",
        "agent+in:name,description,topics",
    ]
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-knowledge-base",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    seen: set[str] = set()
    items: list[dict] = []

    for query in queries:
        url = f"{GITHUB_SEARCH_API}?q={query}+created:>{week_ago}&sort=stars&order=desc&per_page={limit}"
        logger.info("GitHub Search: %s", query)

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.warning("GitHub API 请求失败: %s", e)
            continue

        for repo in data.get("items", []):
            full_name = repo.get("full_name", "")
            if full_name in seen:
                continue
            seen.add(full_name)

            description = repo.get("description") or ""
            if not _is_ai_related(full_name, description):
                continue

            items.append({
                "title": full_name,
                "url": repo.get("html_url", ""),
                "source": "github-trending",
                "popularity": repo.get("stargazers_count", 0),
                "summary": description[:200] if description else "",
            })

        time.sleep(2)

    items.sort(key=lambda x: x["popularity"], reverse=True)
    logger.info("GitHub 采集: %d 条", len(items))
    return items


def _parse_rss(xml_text: str) -> list[dict[str, str]]:
    """用正则解析 RSS XML，提取条目。

    Args:
        xml_text: RSS XML 文本。

    Returns:
        条目列表，每项含 title, link, description。
    """
    items: list[dict[str, str]] = []
    blocks = re.findall(r"<item>(.*?)</item>", xml_text, re.DOTALL)

    for block in blocks:
        title_m = re.search(r"<title>(.*?)</title>", block, re.DOTALL)
        link_m = re.search(r"<link>(.*?)</link>", block, re.DOTALL)
        desc_m = re.search(r"<description>(.*?)</description>", block, re.DOTALL)

        title = title_m.group(1).strip() if title_m else ""
        link = link_m.group(1).strip() if link_m else ""
        desc = desc_m.group(1).strip() if desc_m else ""

        title = re.sub(r"<[^>]+>", "", title)
        desc = re.sub(r"<[^>]+>", "", desc)

        if title and link:
            items.append({"title": title, "link": link, "description": desc[:300]})

    return items


def collect_rss(limit: int = 20) -> list[dict[str, Any]]:
    """从 RSS 源采集 AI 相关内容。

    Args:
        limit: 每个源的最大采集数量。

    Returns:
        标准化条目列表。
    """
    items: list[dict] = []

    for feed_name, feed_url in RSS_FEEDS.items():
        logger.info("RSS 采集: %s", feed_name)
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(feed_url)
                resp.raise_for_status()
                entries = _parse_rss(resp.text)
        except httpx.HTTPError as e:
            logger.warning("RSS 请求失败 (%s): %s", feed_name, e)
            continue

        for entry in entries[:limit]:
            title = entry.get("title", "")
            description = entry.get("description", "")
            if not _is_ai_related(title, description):
                continue

            items.append({
                "title": title,
                "url": entry.get("link", ""),
                "source": feed_name,
                "popularity": 0,
                "summary": description[:200],
            })

    logger.info("RSS 采集: %d 条", len(items))
    return items


def save_raw(items: list[dict], source_label: str) -> Path:
    """将采集数据保存到 knowledge/raw/。

    Args:
        items: 条目列表。
        source_label: 来源标签。

    Returns:
        写入的文件路径。
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    filepath = RAW_DIR / f"{source_label}-{today}.json"

    data = {
        "source": source_label,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("已保存原始数据: %s (%d 条)", filepath, len(items))
    return filepath


# ═══════════════════════════════════════════
# Step 2: 分析
# ═══════════════════════════════════════════


ANALYZE_PROMPT = """你是一个技术内容分析助手。请分析以下技术条目，返回 JSON 格式（仅 JSON，不含其他文字）：

{{
  "summary": "一句话中文摘要（不超过 100 字）",
  "relevance_score": 评分1-10,
  "tags": ["标签1", "标签2", "标签3"],
  "tech_highlights": ["技术亮点1", "技术亮点2"]
}}

评分标准：
- 9-10：突破性进展
- 7-8：对个人技术栈直接有帮助
- 5-6：值得了解
- 1-4：参考价值有限

标签使用英文小写连字符格式，如 agent、llm、open-source。

技术条目：
标题: {title}
来源: {source}
描述: {description}"""


def _extract_json(text: str) -> dict | None:
    """从 LLM 返回文本中提取 JSON。

    Args:
        text: LLM 返回的原始文本。

    Returns:
        解析后的字典，失败返回 None。
    """
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def analyze_item(
    item: dict[str, Any],
    provider: Any,
    dry_run: bool = False,
) -> dict[str, Any]:
    """调用 LLM 分析单条内容。

    Args:
        item: 待分析的条目（含 title, source, summary）。
        provider: LLMProvider 实例。
        dry_run: 干跑模式。

    Returns:
        分析后的条目，新增 analysis 字段。
    """
    if dry_run:
        item["analysis"] = {
            "summary": item.get("summary", "")[:100],
            "relevance_score": 5,
            "tags": ["ai", "auto-generated"],
            "tech_highlights": ["dry-run mode"],
        }
        return item

    prompt = ANALYZE_PROMPT.format(
        title=item.get("title", ""),
        source=item.get("source", ""),
        description=item.get("summary", "")[:500],
    )
    messages = [{"role": "user", "content": prompt}]

    response = chat_with_retry(provider, messages, temperature=0.5, max_tokens=1024)
    if response is None:
        logger.warning("LLM 分析失败: %s", item.get("title"))
        item["error"] = True
        return item

    parsed = _extract_json(response.content)
    if parsed is None:
        logger.warning("LLM 返回非 JSON: %s", response.content[:100])
        item["error"] = True
        return item

    item["analysis"] = parsed
    logger.info("分析完成: %s (score=%s)", item.get("title"), parsed.get("relevance_score"))
    return item


# ═══════════════════════════════════════════
# Step 3: 整理
# ═══════════════════════════════════════════


def _generate_id(item: dict[str, Any]) -> str:
    """根据条目信息生成唯一 ID。

    Args:
        item: 条目数据。

    Returns:
        ID 字符串，格式 {date}-{source_short}-{slug}。
    """
    today = date.today().isoformat()
    source = item.get("source", "unknown")
    source_short = source.replace("-trending", "").replace("arxiv-cs-", "").replace("-", "")
    title = item.get("title", "untitled")
    slug = _slugify(title)
    return f"{today}-{source_short}-{slug}"


def organize(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """整理条目：去重、标准化格式、补充必填字段。

    Args:
        items: 分析后的条目列表。

    Returns:
        整理后的规范化条目列表。
    """
    seen_urls: set[str] = set()
    result: list[dict] = []
    today = date.today().isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()

    for item in items:
        if item.get("error"):
            continue

        url = item.get("url", "")
        if url in seen_urls:
            logger.debug("去重跳过: %s", url)
            continue
        seen_urls.add(url)

        analysis = item.get("analysis", {})
        tags = analysis.get("tags", [])
        if isinstance(tags, list):
            tags = [_slugify(t) for t in tags if isinstance(t, str)]

        article = {
            "id": _generate_id(item),
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "source_url": url,
            "collected_at": now_iso,
            "summary": analysis.get("summary", item.get("summary", ""))[:200],
            "analysis": {
                "tech_highlights": analysis.get("tech_highlights", []),
                "relevance_score": analysis.get("relevance_score", 5),
            },
            "tags": tags,
            "status": "reviewed",
        }
        result.append(article)

    logger.info("整理完成: %d/%d 条保留", len(result), len(items))
    return result


# ═══════════════════════════════════════════
# Step 4: 保存
# ═══════════════════════════════════════════


def save_articles(
    articles: list[dict[str, Any]],
    dry_run: bool = False,
) -> list[Path]:
    """将文章保存为独立 JSON 文件到 knowledge/articles/。

    Args:
        articles: 结构化文章列表。
        dry_run: 干跑模式，不实际写入。

    Returns:
        写入的文件路径列表。
    """
    paths: list[Path] = []
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    for article in articles:
        filepath = ARTICLES_DIR / f"{article['id']}.json"
        if dry_run:
            logger.info("[dry-run] 将写入: %s", filepath)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(article, f, ensure_ascii=False, indent=2)
        paths.append(filepath)

    logger.info("保存完成: %d 篇文章", len(articles))
    return paths


# ═══════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════


def run_pipeline(
    sources: list[str],
    limit: int = 20,
    dry_run: bool = False,
) -> dict[str, Any]:
    """执行四步流水线。

    Args:
        sources: 采集源列表 (github, rss)。
        limit: 每个源的采集数量上限。
        dry_run: 干跑模式，跳过 LLM 调用和文件写入。

    Returns:
        统计信息字典。
    """
    stats: dict[str, Any] = {
        "collected": 0,
        "analyzed": 0,
        "organized": 0,
        "saved": 0,
    }

    # Step 1: 采集
    all_items: list[dict] = []
    for src in sources:
        if src == "github":
            items = collect_github(limit=limit)
        elif src == "rss":
            items = collect_rss(limit=limit)
        else:
            logger.warning("未知采集源: %s", src)
            continue
        all_items.extend(items)

    stats["collected"] = len(all_items)
    logger.info("=== Step 1 采集完成: %d 条 ===", stats["collected"])

    if not all_items:
        logger.warning("未采集到任何内容")
        return stats

    save_raw(all_items, "-".join(sources))

    # Step 2: 分析
    provider = None
    if not dry_run:
        try:
            provider = create_provider()
        except ValueError as e:
            logger.error("LLM 初始化失败: %s", e)
            logger.info("继续以 dry-run 模式分析")
            dry_run = True

    analyzed: list[dict] = []
    for i, item in enumerate(all_items):
        logger.info("分析 %d/%d: %s", i + 1, len(all_items), item.get("title"))
        result = analyze_item(item, provider, dry_run=dry_run)
        analyzed.append(result)
        if not dry_run and i < len(all_items) - 1:
            time.sleep(1)

    stats["analyzed"] = sum(1 for a in analyzed if not a.get("error"))
    logger.info("=== Step 2 分析完成: %d 条 ===", stats["analyzed"])

    # Step 3: 整理
    articles = organize(analyzed)
    stats["organized"] = len(articles)
    logger.info("=== Step 3 整理完成: %d 条 ===", stats["organized"])

    # Step 4: 保存
    paths = save_articles(articles, dry_run=dry_run)
    stats["saved"] = len(paths)
    logger.info("=== Step 4 保存完成: %d 篇 ===", stats["saved"])

    return stats


def main() -> int:
    """CLI 入口。

    Returns:
        0 成功，1 失败。
    """
    parser = argparse.ArgumentParser(
        description="AI 知识库自动化流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pipeline/pipeline.py --sources github,rss --limit 20
  python pipeline/pipeline.py --sources github --limit 5
  python pipeline/pipeline.py --sources rss --limit 10
  python pipeline/pipeline.py --sources github --limit 5 --dry-run
        """,
    )
    parser.add_argument(
        "--sources",
        type=str,
        default="github",
        help="采集源，逗号分隔: github, rss (默认: github)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="每个源的最大采集数量 (默认: 20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干跑模式：跳过 LLM 调用，不写文件",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细日志输出 (DEBUG 级别)",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    valid_sources = {"github", "rss"}
    if not set(sources) & valid_sources:
        logger.error("无效采集源: %s，有效值: %s", sources, valid_sources)
        return 1

    logger.info("=" * 50)
    logger.info("流水线启动: sources=%s limit=%d dry_run=%s", sources, args.limit, args.dry_run)
    logger.info("=" * 50)

    try:
        stats = run_pipeline(sources, limit=args.limit, dry_run=args.dry_run)
    except KeyboardInterrupt:
        logger.info("用户中断")
        return 1
    except Exception as e:
        logger.exception("流水线异常: %s", e)
        return 1

    logger.info("=" * 50)
    logger.info(
        "流水线完成: 采集=%d 分析=%d 整理=%d 保存=%d",
        stats["collected"], stats["analyzed"], stats["organized"], stats["saved"],
    )
    logger.info("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
