"""知识条目 JSON 文件格式校验工具。

用法：python hooks/validate_json.py <json_file> [json_file2 ...]
支持单文件和多文件（含通配符 *.json）两种输入模式。
校验通过 exit 0，失败 exit 1 并输出错误列表和汇总统计。
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REQUIRED_FIELDS: dict[str, type] = {
    "id": str,
    "title": str,
    "source_url": str,
    "summary": str,
    "tags": list,
    "status": str,
}

VALID_STATUSES = frozenset({"draft", "review", "published", "archived"})
VALID_AUDIENCES = frozenset({"beginner", "intermediate", "advanced"})
ID_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}-[a-z][a-z0-9]*(-[a-z0-9]+)*-[a-z][a-z0-9-]+$"
)
URL_PATTERN = re.compile(r"^https?://")


def _find_value(data: dict[str, Any], key: str) -> Any:
    """递归搜索嵌套字典中的指定键，返回第一个匹配值。

    Args:
        data: 待搜索的字典。
        key: 目标键名。

    Returns:
        匹配到的值，未找到返回 None。
    """
    if key in data:
        return data[key]
    for value in data.values():
        if isinstance(value, dict):
            result = _find_value(value, key)
            if result is not None:
                return result
    return None


def validate_single(filepath: Path) -> list[str]:
    """校验单个知识条目 JSON 文件。

    Args:
        filepath: JSON 文件路径。

    Returns:
        错误信息列表，为空表示校验通过。
    """
    errors: list[str] = []
    label = str(filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"{label}: JSON 解析失败 — {e}"]
    except OSError as e:
        return [f"{label}: 文件读取失败 — {e}"]

    if not isinstance(data, dict):
        return [f"{label}: 根元素应为 JSON 对象，实际为 {type(data).__name__}"]

    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"{label}: 缺少必填字段 '{field}'")
        elif not isinstance(data[field], expected_type):
            errors.append(
                f"{label}: 字段 '{field}' 类型错误，"
                f"期望 {expected_type.__name__}，实际 {type(data[field]).__name__}"
            )

    if errors:
        return errors

    item_id: str = data["id"]
    if not ID_PATTERN.match(item_id):
        errors.append(
            f"{label}: ID 格式错误 '{item_id}'，"
            f"期望格式 {{YYYY-MM-DD}}-{{source}}-{{slug}}，如 2026-06-24-github-langgraph"
        )

    status: str = data["status"]
    if status not in VALID_STATUSES:
        errors.append(
            f"{label}: status 值无效 '{status}'，"
            f"有效值: {', '.join(sorted(VALID_STATUSES))}"
        )

    source_url: str = data["source_url"]
    if not URL_PATTERN.match(source_url):
        errors.append(
            f"{label}: source_url 格式无效 '{source_url}'，"
            f"需以 http:// 或 https:// 开头"
        )

    summary: str = data["summary"]
    if len(summary) < 20:
        errors.append(f"{label}: summary 长度不足 ({len(summary)} 字)，最少 20 字")

    tags: list = data["tags"]
    if len(tags) < 1:
        errors.append(f"{label}: tags 至少需要 1 个标签")

    score = _find_value(data, "relevance_score") or _find_value(data, "score")
    if score is not None:
        if not isinstance(score, (int, float)):
            errors.append(
                f"{label}: score 类型错误，期望 int/float，实际 {type(score).__name__}"
            )
        elif not (1 <= score <= 10):
            errors.append(f"{label}: score 值 {score} 不在 1-10 范围内")

    audience = _find_value(data, "audience")
    if audience is not None:
        if not isinstance(audience, str):
            errors.append(
                f"{label}: audience 类型错误，期望 str，实际 {type(audience).__name__}"
            )
        elif audience not in VALID_AUDIENCES:
            errors.append(
                f"{label}: audience 值无效 '{audience}'，"
                f"有效值: {', '.join(sorted(VALID_AUDIENCES))}"
            )

    return errors


_SEARCH_DIRS = ("knowledge/articles", "knowledge/raw", ".")


def _try_resolve(arg: str, search_dir: str) -> Path | None:
    """在指定目录下尝试匹配单个文件或通配符。

    Args:
        arg: 命令行参数（可能是字面量路径或通配符）。
        search_dir: 搜索基准目录。

    Returns:
        匹配到的 Path，未找到返回 None。
    """
    base = Path(search_dir)
    filename = Path(arg).name
    has_glob = any(ch in arg for ch in ("*", "?", "["))

    if has_glob:
        for pattern in (arg, filename):
            matched = list(base.glob(pattern))
            if matched:
                return matched[0].resolve()
        return None

    for candidate_path in (base / arg, base / filename):
        if candidate_path.is_file() and candidate_path.suffix == ".json":
            return candidate_path.resolve()
    return None


def expand_globs(args: list[str]) -> list[Path]:
    """展开通配符并收集 JSON 文件路径，支持回退目录搜索。

    先尝试原始路径，再依次尝试 knowledge/articles/、knowledge/raw/ 目录。
    支持字面量路径和通配符，去重排序后返回。

    Args:
        args: 命令行参数列表。

    Returns:
        去重排序后的 Path 列表。
    """
    seen: set[Path] = set()
    result: list[Path] = []

    for arg in args:
        found = False
        for search_dir in _SEARCH_DIRS:
            resolved = _try_resolve(arg, search_dir)
            if resolved is not None and resolved not in seen:
                seen.add(resolved)
                result.append(resolved)
                found = True
        if not found:
            logger.warning("未找到文件: %s", arg)

    result.sort()
    return result


def main() -> int:
    """入口函数，遍历文件执行校验并输出汇总结果。

    Returns:
        0 表示全部通过，1 表示存在校验失败。
    """
    if len(sys.argv) < 2:
        logger.error("用法: python hooks/validate_json.py <json_file> [json_file2 ...]")
        return 1

    files = expand_globs(sys.argv[1:])
    if not files:
        logger.error("未找到任何 JSON 文件")
        return 1

    total_errors = 0
    passed = 0
    failed_files: list[Path] = []

    for filepath in files:
        errors = validate_single(filepath)
        if errors:
            total_errors += len(errors)
            failed_files.append(filepath)
            for err in errors:
                logger.error(err)
        else:
            logger.info(f"✓ {filepath}")
            passed += 1

    logger.info("=" * 50)
    logger.info(f"校验完成: {passed}/{len(files)} 文件通过")
    if failed_files:
        logger.info(f"失败文件: {len(failed_files)}")
        for fp in failed_files:
            logger.info(f"  - {fp}")
    logger.info(f"错误总数: {total_errors}")

    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    sys.exit(main())
