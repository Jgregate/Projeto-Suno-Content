"""Cliente de LLM: parâmetros por modelo e estimativa de custo (sem rede)."""

import pytest

from backend.llm import _retry_after, estimate_cost, load_prices, supports_reasoning_effort


def test_reasoning_effort_only_for_reasoning_models():
    assert supports_reasoning_effort("groq:openai/gpt-oss-20b")
    assert supports_reasoning_effort("groq:openai/gpt-oss-120b")
    assert not supports_reasoning_effort("groq:qwen/qwen3.8-27b")
    assert not supports_reasoning_effort("anthropic:claude-haiku-5-5")


def test_prices_file_is_valid_and_cost_is_linear():
    prices = load_prices()
    for model, price in prices.items():
        assert ":" in model and {"input_per_mtok", "output_per_mtok"} <= set(price)
    model = next(iter(prices))
    one = estimate_cost(model, 1_000_000, 0)
    assert one == prices[model]["input_per_mtok"]
    assert estimate_cost(model, 2_000_000, 0) == 2 * one
    assert estimate_cost("modelo:desconhecido", 10**6, 10**6) == 0.0


@pytest.mark.parametrize(
    "message, low, high",
    [("Please try again in 7.5s", 7.5, 8.6), ("try again in 2m3s", 60, 61), ("try again in 1h2m3s", 60, 61), ("Please retry in 23.4s.", 23.4, 24.5), ("erro qualquer", 2.0, 3.1)],
)
def test_retry_after_parses_provider_hint_and_caps_at_60s(message, low, high):
    assert low <= _retry_after(Exception(message), 0) <= high


def test_gemini_resource_exhausted_counts_as_rate_limit():
    from backend.llm import _is_rate_limit

    class ClientError(Exception):
        code = 429

    assert _is_rate_limit(ClientError("429 RESOURCE_EXHAUSTED. Quota exceeded"))
    assert not _is_rate_limit(ValueError("schema inválido"))
