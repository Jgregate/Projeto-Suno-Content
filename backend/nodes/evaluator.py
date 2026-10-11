"""Nó Hybrid Evaluator + decisão do reflection loop.

A cada volta:
1. Avalia, em paralelo, só as células cuja tentativa atual ainda não tem relatório.
2. Grava a tentativa no histórico (texto, relatório, nota agregada, regressões, custo).
3. Decide por célula: aprovada -> fecha; atingiu o máximo -> fecha com a melhor;
   nota agregada não subiu >= epsilon -> fecha (parada antecipada); senão -> refiner.
Células fechadas sem aprovação entregam a tentativa de melhor nota agregada.
"""

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Protocol

from backend.config import settings
from backend.evaluator.aggregate import aggregate_score, regressions
from backend.schemas import AttemptRecord, CellStatus, ExtractionResult, GeneratedContent, GraphState, NodeRun, SourceDocument


class Evaluates(Protocol):
    def evaluate(self, output: GeneratedContent, source: SourceDocument, extraction: ExtractionResult | None): ...


def close_cell(history: list[AttemptRecord], reason: str) -> CellStatus:
    last = history[-1]
    if reason == "aprovado":
        status, delivered = ("aprovado" if last.attempt == 1 else f"aprovado_apos_{last.attempt - 1}"), last
    else:
        status = "reprovado_final"
        delivered = max(history, key=lambda h: (h.aggregate_score, -h.attempt))
    return CellStatus(
        status=status,
        attempts=last.attempt,
        delivered_attempt=delivered.attempt,
        best_score=max(h.aggregate_score for h in history),
        stop_reason=reason,
        regressions=sorted({r for h in history for r in h.regressions}),
    )


def _attempt_record(state: GraphState, out: GeneratedContent, ev, previous: AttemptRecord | None) -> AttemptRecord:
    report = ev.report
    regs = regressions(previous.report, report) if previous else []
    if regs:
        report.flags.append("regressao:" + ",".join(regs))
    gen_runs = [
        r for r in state.node_log
        if r.cell == out.key and r.node in ("formatter", "refiner") and (r.attempt or 1) == out.attempt
    ]
    runs = gen_runs + list(ev.runs)
    return AttemptRecord(
        attempt=out.attempt,
        content=out,
        report=report,
        aggregate_score=aggregate_score(report),
        injected_feedback=previous.report.feedback if previous else "",
        regressions=regs,
        input_tokens=sum(r.input_tokens for r in runs),
        output_tokens=sum(r.output_tokens for r in runs),
        cost_usd=round(sum(r.cost_usd for r in runs), 6),
        latency_ms=round(sum(r.latency_ms for r in runs), 1),
    )


def make_evaluator(
    hybrid: Evaluates, max_attempts: int | None = None, epsilon: float | None = None
) -> Callable[[GraphState], dict]:
    max_attempts = max_attempts or settings.max_retries
    epsilon = settings.reflection_epsilon if epsilon is None else epsilon

    def evaluator(state: GraphState) -> dict:
        pending = [
            out for key, out in state.outputs.items()
            if not any(r.attempt == out.attempt for r in state.reports.get(key, []))
        ]
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=max(1, len(pending))) as pool:
            results = list(pool.map(lambda out: hybrid.evaluate(out, state.document, state.extraction), pending))

        reports, history, final, outputs, runs, to_refine = {}, {}, {}, {}, [], []
        for out, ev in zip(pending, results, strict=True):
            for r in ev.runs:
                r.attempt = out.attempt
            runs += ev.runs
            hist = list(state.history.get(out.key, []))
            record = _attempt_record(state, out, ev, hist[-1] if hist else None)
            hist.append(record)
            history[out.key] = hist
            reports[out.key] = [*state.reports.get(out.key, []), record.report]

            if record.report.passed:
                final[out.key] = close_cell(hist, "aprovado")
            elif out.attempt >= max_attempts:
                final[out.key] = close_cell(hist, "max_tentativas")
            elif len(hist) >= 2 and record.aggregate_score - hist[-2].aggregate_score < epsilon:
                final[out.key] = close_cell(hist, "estagnou")
            else:
                to_refine.append(out.key)

        # células cujo refino falhou (o refiner devolve em to_refine): fecham com o que têm
        for key in state.to_refine:
            if key not in history and state.history.get(key):
                final[key] = close_cell(state.history[key], "erro_refino")

        # célula fechada sem aprovação entrega a melhor tentativa
        all_history = {**state.history, **history}
        for key, status in final.items():
            if status.delivered_attempt != all_history[key][-1].attempt:
                outputs[key] = next(h.content for h in all_history[key] if h.attempt == status.delivered_attempt)

        wall = NodeRun(node="evaluator", latency_ms=round((time.perf_counter() - start) * 1000, 1))
        return {
            "reports": reports,
            "history": history,
            "final_status": final,
            "outputs": outputs,
            "attempts": {out.key: out.attempt for out in pending},
            "to_refine": sorted(to_refine),
            "node_log": [*runs, wall],  # "evaluator" = tempo real do nó; "evaluator:*" = por célula
        }

    return evaluator


def route_after_eval(state: GraphState) -> Literal["approve", "retry"]:
    return "retry" if state.to_refine else "approve"
