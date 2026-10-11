"""Chamada de LLM com telemetria (tokens, custo estimado, latência)."""

import logging
import time
from typing import TypeVar

from pydantic import BaseModel

from backend.llm import LLMClient, estimate_cost
from backend.schemas import NodeRun

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger("suno")


def call_llm(
    node: str, cell: str | None, llm: LLMClient, schema: type[T], system: str, user: str
) -> tuple[T, NodeRun]:
    start = time.perf_counter()
    result = llm.structured(schema, system, user)
    latency_ms = (time.perf_counter() - start) * 1000
    run = NodeRun(
        node=node,
        cell=cell,
        model=llm.model_id,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=estimate_cost(llm.model_id, result.input_tokens, result.output_tokens),
        latency_ms=round(latency_ms, 1),
    )
    log.info("%s %s | %d+%d tok | %.0f ms", node, cell or "", run.input_tokens, run.output_tokens, latency_ms)
    return result.parsed, run


def call_llm_with_fallback(
    node: str, cell: str | None, llm: LLMClient, fallback: LLMClient | None, schema: type[T], system: str, user: str
) -> tuple[T, NodeRun, str | None]:
    """Como `call_llm`, mas se o modelo principal não entregar o schema (ValueError), tenta uma vez o `fallback`.

    Devolve (saída, telemetria, aviso). O aviso registra a troca de modelo; sem fallback, o erro sobe.
    """
    try:
        parsed, run = call_llm(node, cell, llm, schema, system, user)
        return parsed, run, None
    except ValueError as exc:
        if fallback is None or fallback is llm:
            raise
        notice = warn(f"[{cell}] {node}: {llm.model_id} não entregou {schema.__name__}; repetindo com {fallback.model_id} ({str(exc)[:120]})")
        parsed, run = call_llm(node, cell, fallback, schema, system, user)
        return parsed, run, notice


def warn(message: str) -> str:
    """Loga o aviso e devolve a mesma string para ir ao estado (`warnings`)."""
    log.warning(message)
    return message
