"""Clientes de LLM por papel (fast, strong, judge, claims).

Cada papel é configurado no .env como "provedor:modelo" e resolvido por
`init_chat_model`. Os nós dependem apenas do protocolo `LLMClient`.
"""

import random
import re
import time
import warnings
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, Protocol, TypeVar

import yaml
from pydantic import BaseModel

from backend.config import PRICES_PATH, settings

# Modelos Gemini com amostragem fixa ignoram `temperature`; o aviso se repetiria a cada chamada.
warnings.filterwarnings("ignore", message=r".*uses fixed sampling defaults.*")

T = TypeVar("T", bound=BaseModel)
Role = Literal["fast", "strong", "judge", "claims"]


@dataclass
class LLMResult:
    parsed: Any
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient(Protocol):
    model_id: str

    def structured(self, schema: type[T], system: str, user: str) -> LLMResult: ...


def _status(exc: Exception) -> int | None:
    # Groq/OpenAI expõem `status_code`; o SDK do Gemini usa `code`.
    for value in (getattr(exc, "status_code", None), getattr(exc, "code", None),
                  getattr(getattr(exc, "response", None), "status_code", None)):
        if isinstance(value, int):
            return value
    return None


def _is_rate_limit(exc: Exception) -> bool:
    return _status(exc) == 429 or "RateLimit" in type(exc).__name__ or "RESOURCE_EXHAUSTED" in str(exc)


def _is_bad_generation(exc: Exception) -> bool:
    """Erro 400 causado por JSON ou tool call inválido gerado pelo modelo (ex.: `tool_use_failed` no Groq)."""
    text = str(exc)
    return _status(exc) == 400 and any(k in text for k in ("tool_use_failed", "json_validate_failed", "did not call a tool"))


def _retry_after(exc: Exception, attempt: int) -> float:
    """Espera indicada pelo provedor ("try again in 7.5s") ou backoff exponencial, até 60 s."""
    match = re.search(r"(?:try again|retry) in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", str(exc), re.IGNORECASE)
    if match:
        hours, minutes, seconds = match.groups()
        wait = int(hours or 0) * 3600 + int(minutes or 0) * 60 + float(seconds)
    else:
        wait = 2.0 * 2**attempt
    return min(60.0, wait + random.uniform(0.2, 1.0))


def supports_reasoning_effort(model_id: str) -> bool:
    """Modelos de raciocínio que aceitam `reasoning_effort` (low/medium/high)."""
    return "gpt-oss" in model_id


class LangChainLLM:
    """Saída estruturada via `with_structured_output`.

    Saída que não valida no schema é reenviada com o erro de validação (até 3 tentativas).
    Respostas 429 aguardam o tempo indicado pelo provedor. No Groq usa `json_schema`, que é
    mais estável que tool calling nos modelos abertos.
    """

    MAX_BAD_OUTPUTS = 3
    MAX_RATE_LIMIT_WAITS = 6
    _method: str | None = None  # método de saída estruturada; None = padrão do provedor

    def __init__(self, model_id: str, temperature: float, reasoning_effort: str = "") -> None:
        from langchain.chat_models import init_chat_model

        self.model_id = model_id
        extra = {"reasoning_effort": reasoning_effort} if reasoning_effort and supports_reasoning_effort(model_id) else {}
        self._model = init_chat_model(model_id, temperature=temperature, **extra)
        self._method = "json_schema" if model_id.startswith("groq:") else None

    def structured(self, schema: type[T], system: str, user: str) -> LLMResult:
        kwargs = {"method": self._method} if self._method else {}
        runnable = self._model.with_structured_output(schema, include_raw=True, **kwargs)
        messages: list[tuple[str, str]] = [("system", system), ("human", user)]
        tokens_in = tokens_out = 0
        bad = waits = 0
        error: object = None
        while bad < self.MAX_BAD_OUTPUTS:
            try:
                out = runnable.invoke(messages)
            except Exception as exc:
                if _is_rate_limit(exc) and waits < self.MAX_RATE_LIMIT_WAITS:
                    time.sleep(_retry_after(exc, waits))
                    waits += 1
                    continue
                if _is_bad_generation(exc):
                    bad += 1
                    error = exc
                    continue
                raise
            usage = getattr(out["raw"], "usage_metadata", None) or {}
            tokens_in += usage.get("input_tokens", 0)
            tokens_out += usage.get("output_tokens", 0)
            if out["parsed"] is not None:
                return LLMResult(out["parsed"], tokens_in, tokens_out)
            bad += 1
            error = out.get("parsing_error")
            messages.append(("human", f"A saída anterior não validou no schema: {error}. Corrija e responda de novo."))
        raise ValueError(f"{self.model_id}: saída inválida para {schema.__name__} após {bad} tentativas: {str(error)[:300]}")


def get_llm(role: Role, temperature: float | None = None) -> LLMClient:
    """Cliente do papel. `judge` usa o strong se LLM_JUDGE_MODEL estiver vazio; `claims` usa o judge."""
    judge = settings.llm_judge_model or settings.llm_strong_model
    model_id = {
        "fast": settings.llm_fast_model,
        "strong": settings.llm_strong_model,
        "judge": judge,
        "claims": settings.llm_claims_model or judge,
    }[role]
    if model_id.startswith("provider:"):
        var = "LLM_FAST_MODEL" if role == "fast" else "LLM_STRONG_MODEL"
        raise RuntimeError(f"{var} não configurado no .env (formato provedor:modelo).")
    return LangChainLLM(
        model_id, settings.llm_temperature if temperature is None else temperature, settings.llm_reasoning_effort
    )


@lru_cache
def load_prices() -> dict[str, dict[str, float]]:
    if not PRICES_PATH.exists():
        return {}
    return yaml.safe_load(PRICES_PATH.read_text(encoding="utf-8")) or {}


def estimate_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Custo em USD a partir de backend/model_prices.yaml; 0 se o modelo não estiver lá."""
    price = load_prices().get(model_id)
    if not price:
        return 0.0
    return (input_tokens * price["input_per_mtok"] + output_tokens * price["output_per_mtok"]) / 1_000_000
