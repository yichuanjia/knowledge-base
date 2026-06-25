"""Hacker News API 客户端 — 获取热门故事及详情。"""

import json
import logging
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

HN_API = "https://hacker-news.firebaseio.com/v0"
MAX_RETRIES = 3
RETRY_BACKOFF = (1, 2, 4)


def _fetch_json(url: str) -> dict | list | None:
    """带重试的 HTTP GET 请求，返回解析后的 JSON。

    Args:
        url: 请求 URL。

    Returns:
        解析后的 JSON 对象；所有重试失败返回 None。
    """
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ai-knowledge-base"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BACKOFF[attempt]
                logger.warning("HN API 请求失败 (第 %d 次重试): %s，%ds 后重试", attempt + 1, e, delay)
                time.sleep(delay)
        except json.JSONDecodeError as e:
            logger.error("HN API 返回非 JSON 数据: %s", e)
            return None
    logger.error("HN API 请求全部重试失败: %s", last_error)
    return None


def get_top_stories(limit: int = 50) -> list[int]:
    """获取 Hacker News 热门故事 ID 列表。

    Args:
        limit: 返回的 ID 数量上限。

    Returns:
        故事 ID 列表；请求失败返回空列表。
    """
    url = f"{HN_API}/topstories.json"
    data = _fetch_json(url)
    if isinstance(data, list):
        return [int(x) for x in data[:limit]]
    logger.error("HN topstories 返回意外格式: %s", type(data))
    return []


def get_story(item_id: int) -> dict | None:
    """获取单条 HN 故事详情。

    Args:
        item_id: 故事 ID。

    Returns:
        故事详情字典；请求失败返回 None。
    """
    url = f"{HN_API}/item/{item_id}.json"
    return _fetch_json(url)


def get_stories_batch(item_ids: list[int], max_workers: int = 8) -> list[dict]:
    """并发批量获取 HN 故事详情。

    Args:
        item_ids: 故事 ID 列表。
        max_workers: 并发线程数。

    Returns:
        成功获取的故事详情列表。
    """
    stories: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_id = {executor.submit(get_story, sid): sid for sid in item_ids}
        for future in as_completed(future_to_id):
            try:
                result = future.result()
                if result is not None:
                    stories.append(result)
            except Exception as e:
                logger.warning("HN 故事获取异常: %s", e)
    logger.info("HN 批量获取: %d/%d 条成功", len(stories), len(item_ids))
    return stories
