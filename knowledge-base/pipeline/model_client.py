"""统一 LLM 调用客户端。

支持 DeepSeek / Qwen / OpenAI 三种提供商，通过环境变量切换。
基于 httpx 直接调用 OpenAI 兼容 API，无需 openai SDK。
"""

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# --- 提供商配置 ---

_PROVIDER_CONFIGS: dict[str, dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "input_price": "0.27",    # USD / 1M tokens
        "output_price": "1.10",   # USD / 1M tokens
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-max",
        "api_key_env": "DASHSCOPE_API_KEY",
        "input_price": "0.50",
        "output_price": "2.00",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
        "input_price": "2.50",
        "output_price": "10.00",
    },
}

_DEFAULT_PROVIDER = "deepseek"
_MAX_RETRIES = 3
_RETRY_BACKOFF = (1, 2, 4)
_TIMEOUT_SECONDS = 60.0


# --- 数据结构 ---


@dataclass
class Usage:
    """Token 用量统计。

    Attributes:
        prompt_tokens: 输入 token 数。
        completion_tokens: 输出 token 数。
        total_tokens: 总 token 数。
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """LLM 调用响应。

    Attributes:
        content: 模型返回的文本内容。
        usage: Token 用量统计。
    """
    content: str
    usage: Usage


# --- 抽象基类 ---


class LLMProvider(ABC):
    """LLM 提供商抽象基类。

    所有提供商实现必须继承此类并实现 chat 方法。
    """

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """发送对话请求并返回模型响应。

        Args:
            messages: 对话消息列表，每项含 role 和 content。
            temperature: 采样温度 (0-2)。
            max_tokens: 最大输出 token 数。

        Returns:
            LLMResponse 实例。
        """
        ...


# --- OpenAI 兼容实现 ---


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容 API 的通用实现。

    适用于 DeepSeek、Qwen DashScope 等兼容 OpenAI 接口的提供商。

    Attributes:
        provider_name: 提供商标识（deepseek/qwen/openai）。
        base_url: API 基础 URL。
        model: 模型名称。
        api_key: API 密钥。
        input_price: 输入价格 (USD/1M tokens)。
        output_price: 输出价格 (USD/1M tokens)。
    """

    def __init__(self, provider_name: str) -> None:
        """初始化提供商。

        Args:
            provider_name: 提供商标识。

        Raises:
            ValueError: 未知提供商或缺少 API 密钥。
        """
        config = _PROVIDER_CONFIGS.get(provider_name)
        if config is None:
            raise ValueError(
                f"未知提供商 '{provider_name}'，有效值: {list(_PROVIDER_CONFIGS)}"
            )

        api_key = os.environ.get(config["api_key_env"], "")
        if not api_key:
            raise ValueError(
                f"缺少环境变量 {config['api_key_env']}，请设置后重试"
            )

        self.provider_name = provider_name
        self.base_url = config["base_url"]
        self.model = config["model"]
        self.api_key = api_key
        self.input_price = float(config["input_price"])
        self.output_price = float(config["output_price"])

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """发送对话请求到 OpenAI 兼容 API。

        Args:
            messages: 对话消息列表。
            temperature: 采样温度。
            max_tokens: 最大输出 token 数。

        Returns:
            LLMResponse 实例。

        Raises:
            httpx.HTTPStatusError: HTTP 错误。
            httpx.TimeoutException: 请求超时。
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        usage_raw = data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_raw.get("prompt_tokens", 0),
            completion_tokens=usage_raw.get("completion_tokens", 0),
            total_tokens=usage_raw.get("total_tokens", 0),
        )

        return LLMResponse(content=content, usage=usage)


# --- 工厂函数 ---


def get_provider(provider_name: str | None = None) -> LLMProvider:
    """根据环境变量创建 LLM 提供商实例。

    Args:
        provider_name: 提供商标识，若为 None 则从 LLM_PROVIDER 环境变量读取，
                       默认 deepseek。

    Returns:
        LLMProvider 实例。
    """
    name = provider_name or os.environ.get("LLM_PROVIDER", _DEFAULT_PROVIDER)
    logger.info("初始化 LLM 提供商: %s", name)
    return OpenAICompatibleProvider(name)


# --- 重试包装 ---


def chat_with_retry(
    provider: LLMProvider,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> LLMResponse | None:
    """带自动重试的 LLM 调用。

    失败时指数退避重试（1s/2s/4s），全部失败返回 None。

    Args:
        provider: LLM 提供商实例。
        messages: 对话消息列表。
        temperature: 采样温度。
        max_tokens: 最大输出 token 数。

    Returns:
        LLMResponse 实例；全部重试失败返回 None。
    """
    for attempt in range(_MAX_RETRIES):
        try:
            return provider.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except httpx.TimeoutException as e:
            logger.warning("请求超时: %s", e)
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP %d: %s", e.response.status_code, e)
        except Exception as e:
            logger.warning("请求异常: %s (%s)", type(e).__name__, e)

        if attempt < _MAX_RETRIES - 1:
            delay = _RETRY_BACKOFF[attempt]
            logger.info("第 %d/%d 次重试，%ds 后重试", attempt + 1, _MAX_RETRIES, delay)
            time.sleep(delay)

    logger.error("全部 %d 次重试失败", _MAX_RETRIES)
    return None


# --- Token 估算与成本 ---


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数量（启发式算法）。

    中英文混合：粗略按 2.5 字符/token 估算，取整向上。

    Args:
        text: 待估算文本。

    Returns:
        估算的 token 数。
    """
    if not text:
        return 0
    return max(1, -(-len(text) // 2.5))  # 整除向上取整


def estimate_messages_tokens(messages: list[dict[str, str]]) -> int:
    """估算消息列表的总输入 token 数。

    Args:
        messages: 对话消息列表。

    Returns:
        估算的 token 总数。
    """
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
    return total


def calculate_cost(
    provider: LLMProvider,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """根据 token 用量计算 USD 成本。

    Args:
        provider: LLM 提供商实例（需为 OpenAICompatibleProvider）。
        prompt_tokens: 输入 token 数。
        completion_tokens: 输出 token 数。

    Returns:
        USD 成本。

    Raises:
        TypeError: provider 不含定价信息。
    """
    if not isinstance(provider, OpenAICompatibleProvider):
        raise TypeError("成本计算需要 OpenAICompatibleProvider 实例")

    input_cost = (prompt_tokens / 1_000_000) * provider.input_price
    output_cost = (completion_tokens / 1_000_000) * provider.output_price
    return input_cost + output_cost


# --- 便捷函数 ---


def quick_chat(
    prompt: str,
    *,
    system: str = "You are a helpful assistant.",
    provider_name: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str | None:
    """一句话调用 LLM。

    Args:
        prompt: 用户消息内容。
        system: 系统提示词。
        provider_name: 提供商标识，默认从环境变量读取。
        temperature: 采样温度。
        max_tokens: 最大输出 token 数。

    Returns:
        模型返回的文本内容；调用失败返回 None。
    """
    provider = get_provider(provider_name)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    response = chat_with_retry(
        provider, messages, temperature=temperature, max_tokens=max_tokens
    )
    if response is None:
        return None
    logger.info(
        "quick_chat 完成: %d tokens (提示词 %d, 补全 %d), 成本 $%.6f",
        response.usage.total_tokens,
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
        calculate_cost(
            provider,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
        ),
    )
    return response.content


# --- 命令行测试 ---

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    provider_name = os.environ.get("LLM_PROVIDER", _DEFAULT_PROVIDER)
    print(f"提供商: {provider_name}")

    # 测试 provider 初始化
    try:
        provider = get_provider()
        print(f"模型: {provider.model}")  # type: ignore[attr-defined]
    except ValueError as e:
        print(f"跳过测试 (无 API Key): {e}")
        print("用法: LLM_PROVIDER=deepseek DEEPSEEK_API_KEY=xxx python -m pipeline.model_client")
        raise SystemExit(0) from e

    # 测试 Token 估算
    sample = "Hello, how are you? 你好，最近怎么样？"
    est = estimate_tokens(sample)
    print(f"Token 估算: '{sample}' -> {est} tokens")

    # 测试 quick_chat
    print("\n调用 quick_chat ...")
    result = quick_chat("用一句话介绍什么是 LLM Agent", max_tokens=200)
    if result:
        print(f"\n回答: {result}")
    else:
        print("调用失败")
