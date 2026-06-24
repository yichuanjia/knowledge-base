"""知识条目 5 维度质量评分工具。

用法：python hooks/check_quality.py <json_file> [json_file2 ...]
支持单文件和多文件（含通配符 *.json）两种输入模式。
存在 C 级条目或处理错误时返回 exit 1，否则返回 exit 0。
"""

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# --- 常量定义 ---

CHINESE_BUZZWORDS: frozenset[str] = frozenset({
    "赋能", "抓手", "闭环", "打通", "全链路", "底层逻辑",
    "颗粒度", "对齐", "拉通", "沉淀", "强大的", "革命性的",
})

ENGLISH_BUZZWORDS: frozenset[str] = frozenset({
    "groundbreaking", "revolutionary", "game-changing", "cutting-edge",
    "state-of-the-art", "best-in-class", "world-class", "next-generation",
    "disruptive", "paradigm-shift", "synergy", "leverage",
    "holistic", "robust", "scalable", "seamless", "innovative",
})

TECH_KEYWORDS: frozenset[str] = frozenset({
    "llm", "大模型", "agent", "智能体", "rag", "inference", "推理",
    "训练", "training", "fine-tuning", "微调", "transformer",
    "embedding", "向量", "gpu", "cuda", "deepseek", "openai",
    "langchain", "prompt", "mcp", "multimodal", "多模态",
    "open-source", "开源", "diffusion", "generative",
    "reinforcement", "强化学习", "tokenizer", "tokenization",
    "chatbot", "copilot", "api", "cli", "sdk",
    "benchmark", "deployment", "部署", "安全",
})

STANDARD_TAGS: frozenset[str] = frozenset({
    "ai", "llm", "agent", "multi-agent", "machine-learning",
    "deep-learning", "nlp", "rag", "inference", "training",
    "fine-tuning", "prompt", "prompt-engineering",
    "open-source", "python", "api", "tool", "framework",
    "library", "sdk", "cli", "runtime", "model",
    "embedding", "vector", "vector-database",
    "transformer", "diffusion", "generative",
    "gpu", "cuda", "optimization", "serving", "deployment",
    "evaluation", "benchmark", "dataset",
    "chatbot", "copilot", "assistant", "multimodal",
    "vision", "speech", "tts", "stt", "tokenizer",
    "kv-cache", "dashboard", "monitoring",
    "intelligence", "news-aggregation",
    "orchestration", "automation", "workflow",
    "visualization", "animation", "design", "ui",
    "memory", "testing", "security", "scanner",
    "safety", "alignment", "reasoning",
    "langchain", "llamaindex", "langgraph",
    "ollama", "vllm", "openai", "anthropic",
    "claude", "gpt", "llama", "mistral", "gemma",
    "deepseek", "qwen", "mixtral", "gemini", "grok",
    "text-to-image", "text-to-video", "text-to-speech",
    "mcp", "extension", "browser", "mobile",
    "docker", "kubernetes", "linux", "web",
    "javascript", "typescript", "rust", "go", "react",
    "feedback", "analytics", "data", "search", "crawler",
    "sandbox", "isolation", "developer-tools",
    "internet-access", "web-scraping", "social-media",
    "coding-agent", "best-practices", "engineering",
    "code-intelligence", "knowledge-graph",
    "system-prompt", "time-series", "forecasting",
    "foundation-model", "google", "nvidia",
    "video-production", "agentic", "pipeline",
    "audio-generation", "visual-generation",
    "multi-modal", "open-source", "jingdong",
})

VALID_STATUSES = frozenset({"draft", "review", "reviewed", "published", "archived"})

ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]+-\d{8}-\d{3}$")

BAR_WIDTH = 10
OVERALL_BAR_WIDTH = 20


# --- 数据结构 ---


@dataclass
class DimensionScore:
    """单个维度的评分结果。

    Attributes:
        name: 维度名称。
        score: 实际得分。
        max_score: 满分。
        details: 得分说明。
    """
    name: str
    score: float
    max_score: float
    details: str = ""


@dataclass
class QualityReport:
    """单个文件的质量评分报告。

    Attributes:
        filepath: 文件路径。
        dimensions: 各维度评分列表。
        errors: 处理过程中的错误信息。
    """
    filepath: Path
    dimensions: list[DimensionScore] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_score(self) -> float:
        """计算加权总分（满分 100）。"""
        if not self.dimensions:
            return 0.0
        return sum(d.score for d in self.dimensions)

    @property
    def grade(self) -> str:
        """根据总分计算等级 A/B/C。"""
        if self.total_score >= 80:
            return "A"
        elif self.total_score >= 60:
            return "B"
        else:
            return "C"


# --- 辅助函数 ---


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


def _dimension_bar(score: float, max_score: float, width: int) -> str:
    """渲染 Unicode 方块进度条。

    Args:
        score: 实际得分。
        max_score: 满分。
        width: 进度条宽度（字符数）。

    Returns:
        进度条字符串，如 '██████░░░░'。
    """
    if max_score <= 0:
        return "░" * width
    ratio = max(0.0, min(1.0, score / max_score))
    filled = round(ratio * width)
    return "█" * filled + "░" * (width - filled)


def _count_tech_keywords(text: str) -> int:
    """统计文本中匹配到的不同技术关键词数量。

    Args:
        text: 待分析的文本（支持中英文混合）。

    Returns:
        去重后的技术关键词命中数。
    """
    text_lower = text.lower()
    count = 0
    for kw in TECH_KEYWORDS:
        if kw.lower() in text_lower:
            count += 1
    return count


def _find_buzzwords(text: str) -> list[str]:
    """检测文本中包含的空洞词（中英文混合检测，去重）。

    Args:
        text: 待检测的文本。

    Returns:
        发现的空洞词列表（排序）。
    """
    found: set[str] = set()
    text_lower = text.lower()
    for word in CHINESE_BUZZWORDS:
        if word in text:
            found.add(word)
    for word in ENGLISH_BUZZWORDS:
        if word in text_lower:
            found.add(word)
    return sorted(found)


# --- 评分维度实现 ---


def score_summary(data: dict[str, Any]) -> DimensionScore:
    """评分维度 1：摘要质量（满分 25）。

    评分规则：
    - >= 50 字: 20 分基础
    - >= 35 字: 16 分基础
    - >= 20 字: 12 分基础
    - < 20 字: 5 分基础
    - 含技术关键词额外加分，每个 +1，上限 +5
    - 总分上限 25

    Args:
        data: 知识条目数据字典。

    Returns:
        DimensionScore 实例。
    """
    max_score = 25.0
    summary = data.get("summary", "")
    if not isinstance(summary, str):
        return DimensionScore("摘要质量", 0.0, max_score, "summary 字段非字符串")

    length = len(summary)

    if length >= 50:
        base = 20.0
        detail = f"长度充足 ({length}字)"
    elif length >= 35:
        base = 16.0
        detail = f"长度良好 ({length}字)"
    elif length >= 20:
        base = 12.0
        detail = f"长度基本合格 ({length}字)"
    else:
        base = 5.0
        detail = f"长度不足 ({length}字，最低20字)"

    kw_count = _count_tech_keywords(summary)
    bonus = min(float(kw_count), 5.0)
    if bonus > 0:
        detail += f"，含 {int(bonus)} 个技术关键词"

    final_score = min(base + bonus, max_score)
    return DimensionScore("摘要质量", final_score, max_score, detail)


def score_tech_depth(data: dict[str, Any]) -> DimensionScore:
    """评分维度 2：技术深度（满分 25）。

    基于 analysis.relevance_score（1-10）线性映射到 0-25。
    若字段缺失或类型错误则记 0 分。

    Args:
        data: 知识条目数据字典。

    Returns:
        DimensionScore 实例。
    """
    max_score = 25.0
    relevance = _find_value(data, "relevance_score")
    if relevance is None:
        relevance = data.get("score")

    if relevance is None:
        return DimensionScore("技术深度", 0.0, max_score, "缺少 relevance_score 字段")
    if not isinstance(relevance, (int, float)):
        return DimensionScore("技术深度", 0.0, max_score, "relevance_score 类型错误")

    mapped = (relevance / 10.0) * max_score
    final_score = max(0.0, min(max_score, mapped))
    return DimensionScore(
        "技术深度", round(final_score, 1), max_score,
        f"relevance_score={relevance}"
    )


def score_format(data: dict[str, Any]) -> DimensionScore:
    """评分维度 3：格式规范（满分 20）。

    检查 id、title、source_url、status、collected_at 五项，各 4 分。

    Args:
        data: 知识条目数据字典。

    Returns:
        DimensionScore 实例。
    """
    max_score = 20.0
    items_per_check = max_score / 5
    checks: list[tuple[str, bool]] = []

    item_id = data.get("id")
    checks.append((
        "id",
        isinstance(item_id, str) and bool(ID_PATTERN.match(item_id)),
    ))

    title = data.get("title")
    checks.append((
        "title",
        isinstance(title, str) and len(title) > 0,
    ))

    source_url = data.get("source_url")
    checks.append((
        "source_url",
        isinstance(source_url, str) and source_url.startswith(("http://", "https://")),
    ))

    status = data.get("status")
    checks.append((
        "status",
        isinstance(status, str) and status in VALID_STATUSES,
    ))

    collected_at = data.get("collected_at")
    checks.append((
        "collected_at",
        isinstance(collected_at, str) and len(collected_at) > 0,
    ))

    passed = sum(1 for _, ok in checks if ok)
    failed_items = [name for name, ok in checks if not ok]

    detail = f"{passed}/{len(checks)} 项合规"
    if failed_items:
        detail += f"，问题项: {', '.join(failed_items)}"

    return DimensionScore("格式规范", passed * items_per_check, max_score, detail)


def score_tags(data: dict[str, Any]) -> DimensionScore:
    """评分维度 4：标签精度（满分 15）。

    评分规则：
    - 1-3 个标签: 10 分（最佳范围）
    - 4-5 个标签: 7 分
    - >5 个标签: 4 分
    - 0 个标签: 0 分
    - 标准标签匹配率 × 5 作为奖励分，上限 15

    Args:
        data: 知识条目数据字典。

    Returns:
        DimensionScore 实例。
    """
    max_score = 15.0
    tags = data.get("tags", [])
    if not isinstance(tags, list):
        return DimensionScore("标签精度", 0.0, max_score, "tags 字段非列表")

    tag_count = len(tags)
    if tag_count == 0:
        return DimensionScore("标签精度", 0.0, max_score, "无标签")

    if tag_count <= 3:
        count_score = 10.0
    elif tag_count <= 5:
        count_score = 7.0
    else:
        count_score = 4.0

    matching = sum(
        1 for t in tags
        if isinstance(t, str) and t.lower() in STANDARD_TAGS
    )
    validity_bonus = (matching / tag_count) * 5.0

    final_score = min(count_score + validity_bonus, max_score)
    detail = f"{tag_count} 个标签，{matching} 个匹配标准库"
    return DimensionScore("标签精度", round(final_score, 1), max_score, detail)


def score_buzzwords(data: dict[str, Any]) -> DimensionScore:
    """评分维度 5：空洞词检测（满分 15）。

    在 title 和 summary 中检测中英文空洞词，每个唯一空洞词扣 3 分，最低 0 分。

    Args:
        data: 知识条目数据字典。

    Returns:
        DimensionScore 实例。
    """
    max_score = 15.0
    text_parts: list[str] = []
    for field_name in ("title", "summary"):
        value = data.get(field_name, "")
        if isinstance(value, str):
            text_parts.append(value)

    combined = " ".join(text_parts)
    found = _find_buzzwords(combined)

    deduction = len(found) * 3.0
    final_score = max(0.0, max_score - deduction)

    if found:
        detail = f"发现 {len(found)} 个空洞词: {', '.join(found)}"
    else:
        detail = "未发现空洞词"

    return DimensionScore("空洞词检测", final_score, max_score, detail)


# --- 文件处理 ---


def analyze_file(filepath: Path) -> QualityReport:
    """对单个 JSON 文件执行全部 5 个维度评分。

    Args:
        filepath: JSON 文件路径。

    Returns:
        QualityReport 实例，包含各维度得分或错误信息。
    """
    report = QualityReport(filepath=filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        report.errors.append(f"JSON 解析失败: {e}")
        return report
    except OSError as e:
        report.errors.append(f"文件读取失败: {e}")
        return report

    if not isinstance(data, dict):
        report.errors.append("根元素非 JSON 对象")
        return report

    report.dimensions = [
        score_summary(data),
        score_tech_depth(data),
        score_format(data),
        score_tags(data),
        score_buzzwords(data),
    ]
    return report


def expand_globs(args: list[str]) -> list[Path]:
    """展开通配符并收集 JSON 文件路径，去重排序。

    Args:
        args: 命令行参数列表，支持字面量路径和通配符 (*/?/[)。

    Returns:
        去重排序后的 Path 列表。
    """
    seen: set[Path] = set()
    result: list[Path] = []

    for arg in args:
        has_glob = any(ch in arg for ch in ("*", "?", "["))
        if has_glob:
            matched = list(Path().glob(arg))
            if not matched:
                logger.warning("通配符未匹配到文件: %s", arg)
            for p in matched:
                resolved = p.resolve()
                if resolved not in seen and resolved.suffix == ".json":
                    seen.add(resolved)
                    result.append(resolved)
        else:
            path = Path(arg)
            if path.is_file() and path.suffix == ".json":
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    result.append(resolved)
            else:
                logger.warning("文件不存在或非 JSON: %s", arg)

    result.sort()
    return result


# --- 输出渲染 ---


def _print_overall_bar(current: int, total: int) -> None:
    """打印整体处理进度条。

    Args:
        current: 当前已处理数量。
        total: 总文件数量。
    """
    ratio = current / total if total > 0 else 0.0
    filled = round(ratio * OVERALL_BAR_WIDTH)
    bar = "█" * filled + "░" * (OVERALL_BAR_WIDTH - filled)
    print(f"\n[{bar}] {current}/{total}")


def print_report(report: QualityReport) -> None:
    """打印单个文件的评分报告。

    Args:
        report: QualityReport 实例。
    """
    filename = report.filepath.name
    print(f"\n{'─' * 50}")
    print(f"  {filename}")
    print(f"{'─' * 50}")

    if report.errors:
        for err in report.errors:
            print(f"  ✗ {err}")
        return

    for dim in report.dimensions:
        bar = _dimension_bar(dim.score, dim.max_score, BAR_WIDTH)
        print(
            f"  {dim.name:<10} {bar} "
            f"{dim.score:>5.1f}/{dim.max_score:<4.0f}  {dim.details}"
        )

    print(f"  {'─' * 46}")
    print(f"  总分: {report.total_score:.1f}/100  等级: {report.grade}")


def print_summary(reports: list[QualityReport]) -> None:
    """打印汇总统计，含平均分、等级分布、各维度平均分。

    Args:
        reports: 所有文件的评分报告列表。
    """
    valid_reports = [r for r in reports if not r.errors and r.dimensions]
    if not valid_reports:
        print(f"\n{'═' * 50}")
        print(f"  无有效文件可统计")
        print(f"{'═' * 50}")
        return

    avg_score = sum(r.total_score for r in valid_reports) / len(valid_reports)
    grades: dict[str, int] = {"A": 0, "B": 0, "C": 0}
    for r in valid_reports:
        grades[r.grade] += 1

    print(f"\n{'═' * 50}")
    print(f"  汇总统计")
    print(f"{'═' * 50}")
    print(f"  文件总数: {len(reports)}")
    print(f"  有效文件: {len(valid_reports)}")
    print(f"  错误文件: {len(reports) - len(valid_reports)}")
    print(f"  平均分:   {avg_score:.1f}/100")
    print(f"  等级分布: A={grades['A']}  B={grades['B']}  C={grades['C']}")

    dim_names = ["摘要质量", "技术深度", "格式规范", "标签精度", "空洞词检测"]
    dim_maxs = [25.0, 25.0, 20.0, 15.0, 15.0]
    dim_sums = [0.0] * len(dim_names)
    for r in valid_reports:
        for i, dim in enumerate(r.dimensions):
            if i < len(dim_sums):
                dim_sums[i] += dim.score

    print(f"\n  各维度平均分:")
    for i, name in enumerate(dim_names):
        avg = dim_sums[i] / len(valid_reports)
        bar = _dimension_bar(avg, dim_maxs[i], BAR_WIDTH)
        print(f"    {name:<10} {bar} {avg:.1f}/{dim_maxs[i]:.0f}")
    print(f"{'═' * 50}")


# --- 入口 ---


def main() -> int:
    """入口函数。

    Returns:
        0 表示全部通过（无 C 级），1 表示存在 C 级或处理错误。
    """
    if len(sys.argv) < 2:
        logger.error("用法: python hooks/check_quality.py <json_file> [json_file2 ...]")
        return 1

    files = expand_globs(sys.argv[1:])
    if not files:
        logger.error("未找到任何 JSON 文件")
        return 1

    print(f"\n{'═' * 50}")
    print(f"  知识条目质量评分报告")
    print(f"{'═' * 50}")

    reports: list[QualityReport] = []
    total = len(files)

    for i, filepath in enumerate(files, 1):
        _print_overall_bar(i - 1, total)
        report = analyze_file(filepath)
        print_report(report)
        reports.append(report)

    _print_overall_bar(total, total)
    print_summary(reports)

    has_c = any(
        not r.errors and r.dimensions and r.grade == "C"
        for r in reports
    )
    has_error = any(r.errors for r in reports)
    return 1 if (has_c or has_error) else 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    sys.exit(main())
