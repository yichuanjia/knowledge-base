"""MCP Server — 本地知识库搜索服务。

通过 JSON-RPC 2.0 over stdio 协议提供知识库检索能力，
支持关键词搜索、文章详情获取和统计信息查询。
"""

import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ARTICLES_DIR = Path("knowledge/articles")
SERVER_NAME = "knowledge-base-mcp"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"


def _load_articles() -> list[dict[str, Any]]:
    """加载 knowledge/articles/ 下所有 JSON 文件到内存。

    Returns:
        文章字典列表，解析失败的文件被跳过。
    """
    articles: list[dict[str, Any]] = []
    if not ARTICLES_DIR.is_dir():
        logger.warning("文章目录不存在: %s", ARTICLES_DIR)
        return articles

    for filepath in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("id"):
                articles.append(data)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("跳过 %s: %s", filepath.name, e)

    logger.info("已加载 %d 篇文章", len(articles))
    return articles


# ── MCP 工具实现 ──────────────────────────────


def _search_articles(
    articles: list[dict[str, Any]],
    keyword: str,
    limit: int = 5,
) -> str:
    """按关键词搜索文章标题和摘要。

    Args:
        articles: 文章列表。
        keyword: 搜索关键词。
        limit: 返回数量上限。

    Returns:
        JSON 格式的搜索结果文本。
    """
    kw_lower = keyword.lower()
    results: list[dict[str, Any]] = []

    for article in articles:
        title = article.get("title", "")
        summary = article.get("summary", "")
        analysis = article.get("analysis", {})
        if isinstance(analysis, dict):
            summary_from_analysis = analysis.get("summary", "")
            if summary_from_analysis:
                summary = summary_from_analysis

        if kw_lower in title.lower() or kw_lower in summary.lower():
            results.append({
                "id": article.get("id"),
                "title": title,
                "summary": str(summary)[:150],
                "source": article.get("source", ""),
                "tags": article.get("tags", []),
                "relevance_score": (
                    analysis.get("relevance_score")
                    if isinstance(analysis, dict) else None
                ),
            })

    results.sort(
        key=lambda x: x.get("relevance_score") or 0,
        reverse=True,
    )
    results = results[:limit]

    if not results:
        return f"未找到匹配 '{keyword}' 的文章"

    return json.dumps(results, ensure_ascii=False, indent=2)


def _get_article(
    articles: list[dict[str, Any]],
    article_id: str,
) -> str:
    """按 ID 获取文章完整内容。

    Args:
        articles: 文章列表。
        article_id: 文章 ID。

    Returns:
        JSON 格式的文章全文。
    """
    for article in articles:
        if article.get("id") == article_id:
            return json.dumps(article, ensure_ascii=False, indent=2)

    return f"文章不存在: {article_id}"


def _knowledge_stats(articles: list[dict[str, Any]]) -> str:
    """生成知识库统计信息。

    Args:
        articles: 文章列表。

    Returns:
        JSON 格式的统计信息。
    """
    total = len(articles)

    sources: Counter[str] = Counter()
    all_tags: Counter[str] = Counter()
    scores: list[int] = []

    for article in articles:
        source = article.get("source", "unknown")
        sources[source] += 1

        tags = article.get("tags", [])
        for tag in tags:
            if isinstance(tag, str):
                all_tags[tag] += 1

        analysis = article.get("analysis", {})
        score = analysis.get("relevance_score") if isinstance(analysis, dict) else None
        if isinstance(score, (int, float)):
            scores.append(int(score))

    avg_score = sum(scores) / len(scores) if scores else 0.0

    stats = {
        "total_articles": total,
        "average_relevance_score": round(avg_score, 1),
        "sources": dict(sources.most_common()),
        "top_tags": dict(all_tags.most_common(20)),
    }

    return json.dumps(stats, ensure_ascii=False, indent=2)


# ── MCP 协议定义 ──────────────────────────────


TOOLS_DEFINITION = [
    {
        "name": "search_articles",
        "description": "按关键词搜索知识库中的文章标题和摘要，返回匹配结果列表",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词（支持中英文）",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量上限，默认 5",
                },
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "get_article",
        "description": "按文章 ID 获取完整内容，包括分析结果和标签",
        "inputSchema": {
            "type": "object",
            "properties": {
                "article_id": {
                    "type": "string",
                    "description": "文章唯一 ID，如 2026-06-24-github-langgraph",
                },
            },
            "required": ["article_id"],
        },
    },
    {
        "name": "knowledge_stats",
        "description": "获取知识库统计信息：文章总数、来源分布、热门标签、平均评分",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _build_response(request_id: Any, result: Any) -> dict[str, Any]:
    """构建 JSON-RPC 2.0 成功响应。

    Args:
        request_id: 请求 ID。
        result: 响应结果。

    Returns:
        JSON-RPC 响应字典。
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def _build_error(
    request_id: Any,
    code: int,
    message: str,
) -> dict[str, Any]:
    """构建 JSON-RPC 2.0 错误响应。

    Args:
        request_id: 请求 ID。
        code: 错误码。
        message: 错误描述。

    Returns:
        JSON-RPC 错误响应字典。
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def handle_request(
    request: dict[str, Any],
    articles: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """处理单个 JSON-RPC 请求。

    Args:
        request: JSON-RPC 请求字典。
        articles: 文章列表。

    Returns:
        JSON-RPC 响应字典，若是通知则返回 None。
    """
    request_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    # 通知（无 id）不需要响应
    if request_id is None:
        if method == "notifications/initialized":
            logger.debug("收到 initialized 通知")
        return None

    try:
        if method == "initialize":
            return _build_response(request_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            })

        if method == "tools/list":
            return _build_response(request_id, {"tools": TOOLS_DEFINITION})

        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            if tool_name == "search_articles":
                keyword = arguments.get("keyword", "")
                limit = arguments.get("limit", 5)
                result_text = _search_articles(articles, keyword, limit)
            elif tool_name == "get_article":
                article_id = arguments.get("article_id", "")
                result_text = _get_article(articles, article_id)
            elif tool_name == "knowledge_stats":
                result_text = _knowledge_stats(articles)
            else:
                return _build_error(
                    request_id, -32601, f"未知工具: {tool_name}"
                )

            return _build_response(request_id, {
                "content": [{"type": "text", "text": result_text}],
                "isError": False,
            })

        return _build_error(request_id, -32601, f"未知方法: {method}")

    except Exception as e:
        logger.exception("处理请求异常")
        return _build_error(request_id, -32603, str(e))


# ── 主循环 ────────────────────────────────────


def run() -> None:
    """启动 MCP Server 主循环，通过 stdin/stdout 通信。

    每行一个 JSON-RPC 消息，持续读取直到 EOF。
    """
    articles = _load_articles()
    logger.info("MCP Server 启动: %s v%s (%d 篇文章)",
                SERVER_NAME, SERVER_VERSION, len(articles))

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning("JSON 解析失败: %s", e)
            continue

        response = handle_request(request, articles)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    run()
