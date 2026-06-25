"""GitHub API 工具函数 — 获取仓库基本信息。"""

import json
import logging
import os
import urllib.request

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def get_repo_info(owner: str, repo: str) -> dict | None:
    """从 GitHub API 获取指定仓库的基本信息。

    Args:
        owner: 仓库所有者（用户名或组织名）。
        repo: 仓库名称。

    Returns:
        包含 star 数、fork 数、描述等字段的字典；请求失败返回 None。

        {
            "name": str,
            "full_name": str,
            "description": str,
            "stars": int,
            "forks": int,
            "language": str,
            "html_url": str,
        }
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-knowledge-base",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        logger.error("GitHub API 请求失败 [%s]: %s", e.code, e.reason)
        return None
    except urllib.error.URLError as e:
        logger.error("网络请求失败: %s", e.reason)
        return None

    return {
        "name": data.get("name"),
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "language": data.get("language"),
        "html_url": data.get("html_url"),
    }
