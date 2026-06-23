"""采集器 — 从 GitHub Search 和 Hacker News 采集 AI 领域技术动态。"""

import http.client
import json
import logging
import re
import time
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pipeline.hn_api import get_top_stories, get_stories_batch

logger = logging.getLogger(__name__)

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
GITHUB_TOKEN = __import__("os").environ.get("GITHUB_TOKEN", "")
RAW_DIR = Path("knowledge/raw")
ARTICLES_DIR = Path("knowledge/articles")
MAX_RETRIES = 3
RETRY_BACKOFF = (1, 2, 4)

AI_KEYWORDS: list[str] = [
    "ai", "artificial intelligence", "artificial-intelligence",
    "machine learning", "machine-learning", "ml",
    "deep learning", "deep-learning", "dl",
    "llm", "large language model", "large-language-model",
    "nlp", "natural language processing", "natural-language-processing",
    "agent", "ai agent", "multi-agent",
    "rag", "retrieval augmented generation", "retrieval-augmented-generation",
    "embedding", "vector", "vector database", "vector-database",
    "chatbot", "copilot",
    "gpt", "bert", "transformer",
    "diffusion", "generative", "generative ai", "generative-ai",
    "prompt", "prompt engineering", "prompt-engineering",
    "fine-tuning", "fine tuning", "finetuning",
    "inference", "training",
    "neural network", "neural-network",
    "gpu", "cuda",
    "langchain", "llamaindex", "langgraph",
    "crewai", "autogen",
    "openai", "anthropic", "llama", "mistral", "gemma",
    "qwen", "deepseek", "mixtral", "claude", "gemini", "grok",
    "ollama", "vllm",
    "foundation model", "foundation-model",
    "multimodal", "vision language", "vision-language",
    "text-to-image", "text-to-video", "text-to-speech", "tts", "stt",
    "speech recognition", "speech-recognition",
    "mlops", "llmops",
    "mcp", "model context protocol", "model-context-protocol",
    "ocr", "object detection", "image recognition",
    "reinforcement learning", "reinforcement-learning",
    "tokenizer", "tokenization",
    "open source ai", "open-source ai", "open-source-ai",
    "人工智能", "大模型", "机器学习", "深度学习", "智能体",
    "知识图谱", "自然语言处理",
]


def _fetch_json(url: str, extra_headers: dict[str, str] | None = None) -> dict | list | None:
    """带重试的 HTTP GET 请求，返回解析后的 JSON。

    Args:
        url: 请求 URL。
        extra_headers: 额外的 HTTP 请求头。

    Returns:
        解析后的 JSON 对象；所有重试失败返回 None。
    """
    headers = {"User-Agent": "ai-knowledge-base"}
    if extra_headers:
        headers.update(extra_headers)

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if raw:
                    return json.loads(raw.decode())
                logger.warning("空响应: %s", url)
                return None
        except (urllib.error.URLError, urllib.error.HTTPError, http.client.IncompleteRead, OSError) as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BACKOFF[attempt]
                logger.warning("请求失败 (第 %d/%d 次重试): %s，%ds 后重试", attempt + 1, MAX_RETRIES, e, delay)
                time.sleep(delay)
            else:
                logger.error("请求全部重试失败 (%d 次): %s — %s", MAX_RETRIES, e, url)
        except json.JSONDecodeError as e:
            logger.error("返回非 JSON 数据: %s — %s", e, url)
            return None
    return None


def is_ai_related(title: str, description: str = "") -> bool:
    """判断内容是否属于 AI/LLM/Agent 领域。

    使用词边界匹配，防止短关键词子串误匹配（如 renaissance 中的 ai）。

    Args:
        title: 标题。
        description: 描述文本。

    Returns:
        True 表示与 AI 领域相关。
    """
    text = f"{title} {description}".lower()
    for kw in AI_KEYWORDS:
        if len(kw) <= 3:
            if _word_match(text, kw):
                return True
        elif kw in text:
            return True
    return False


def _word_match(text: str, keyword: str) -> bool:
    """词边界匹配，keyword 必须作为完整单词出现。

    Args:
        text: 待搜索文本。
        keyword: 关键词。

    Returns:
        True 表示关键词作为完整单词出现。
    """
    pattern = rf"(?<![a-z0-9-]){re.escape(keyword)}(?![a-z0-9-])"
    return bool(re.search(pattern, text))


def collect_github_trending(per_page: int = 25) -> list[dict[str, Any]]:
    """通过 GitHub Search API 采集近一周的热门 AI 相关仓库。

    使用多个搜索词串行搜索，合并去重后按 stars 降序排列。

    Args:
        per_page: 每次搜索返回的结果数。

    Returns:
        仓库信息列表，每项包含 title, url, source, popularity, summary 字段。
    """
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    search_queries = [
        "ai+in:name,description,topics",
        "llm+in:name,description,topics",
        "agent+in:name,description,topics",
        "deep-learning+OR+machine-learning+in:name,description,topics",
    ]

    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    seen: set[str] = set()
    all_items: list[dict] = []

    for query in search_queries:
        url = f"{GITHUB_SEARCH_API}?q={query}+created:>{week_ago}&sort=stars&order=desc&per_page={per_page}"
        logger.info("GitHub Search: %s (since %s)", query, week_ago)
        data = _fetch_json(url, extra_headers=headers)

        if not isinstance(data, dict) or "items" not in data:
            logger.warning("GitHub Search 无结果: %s", query)
            continue

        for repo in data.get("items", []):
            full_name = repo.get("full_name", "")
            if full_name in seen:
                continue
            seen.add(full_name)

            description = repo.get("description") or ""
            if not is_ai_related(full_name, description):
                continue

            all_items.append({
                "title": full_name,
                "url": repo.get("html_url", ""),
                "source": "github-trending",
                "popularity": repo.get("stargazers_count", 0),
                "summary": description[:200] if description else "",
            })

        time.sleep(3)  # 限速：无 token 10 req/min，留足余量

    all_items.sort(key=lambda x: x["popularity"], reverse=True)
    logger.info("GitHub 采集完成: %d 条 AI 相关仓库", len(all_items))
    return all_items


def collect_hacker_news(limit: int = 50) -> list[dict[str, Any]]:
    """从 Hacker News 采集热门 AI 相关文章。

    拉取 top stories，并发获取详情，用关键词过滤。

    Args:
        limit: 拉取的热门故事数量。

    Returns:
        文章列表，每项包含 title, url, source, popularity, summary 字段。
    """
    story_ids = get_top_stories(limit=limit)
    if not story_ids:
        logger.error("HN 获取热门故事 ID 失败")
        return []

    stories = get_stories_batch(story_ids)
    items: list[dict] = []

    for story in stories:
        title = story.get("title", "")
        if not title:
            continue

        story_url = story.get("url") or f"https://news.ycombinator.com/item?id={story.get('id')}"
        text = story.get("text", "")

        if not is_ai_related(title, text):
            continue

        summary = ""
        if text:
            text_clean = text.replace("&#x2F;", "/").replace("&#x27;", "'")
            text_clean = text_clean.replace("<p>", " ").replace("\n", " ")
            text_clean = " ".join(text_clean.split())
            summary = text_clean[:200]

        items.append({
            "title": title,
            "url": story_url,
            "source": "hacker-news",
            "popularity": story.get("score", 0),
            "summary": summary,
        })

    items.sort(key=lambda x: x["popularity"], reverse=True)
    logger.info("HN 采集完成: %d 条 AI 相关文章", len(items))
    return items


def save_raw_data(items: list[dict[str, Any]], source: str) -> Path:
    """将采集数据保存为 JSON 文件到 knowledge/raw/。

    Args:
        items: 采集条目列表。
        source: 来源标识，如 github-trending 或 hacker-news。

    Returns:
        写入的文件路径。
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()
    filename = f"{source}-{today}.json"
    filepath = RAW_DIR / filename

    data = {
        "source": source,
        "collected_at": now_iso,
        "count": len(items),
        "items": items,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info("已保存 %d 条数据到 %s", len(items), filepath)
    return filepath


def run() -> dict[str, Path]:
    """执行完整采集流程。

    Returns:
        各来源写入的文件路径字典，key 为 source 标识。
    """
    results: dict[str, Path] = {}
    today = date.today().isoformat()

    logger.info("=" * 50)
    logger.info("开始采集 AI 领域技术动态 — %s", today)
    logger.info("=" * 50)

    for label, func, source_name in [
        ("GitHub Trending", collect_github_trending, "github-trending"),
        ("Hacker News", collect_hacker_news, "hacker-news"),
    ]:
        logger.info("--- 采集 %s ---", label)
        try:
            items = func()
        except Exception as e:
            logger.error("%s 采集异常: %s", label, e)
            items = []

        if items:
            filepath = save_raw_data(items, source_name)
            results[source_name] = filepath
        else:
            logger.warning("%s 未采集到有效数据", label)

    logger.info("=" * 50)
    logger.info("采集完成 — 共 %d 个来源有数据", len(results))
    logger.info("=" * 50)

    return results
