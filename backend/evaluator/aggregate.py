"""Nota agregada 0..1 de um EvaluationReport, para o reflection loop.

Usada na parada por estagnação e na escolha da melhor tentativa quando nenhuma aprova.

Por métrica: 1 se aprovada; caso contrário, 1 - |valor - limiar| / max(|limiar|, 1), limitado a [0, 1].
Ex.: Flesch 38 com limiar 60 vale 1 - 22/60 = 0,63; um número sem fonte com limiar 0 vale 0.
Métricas informativas não entram na média.
"""

from backend.schemas import EvaluationReport, MetricResult


def metric_score(m: MetricResult) -> float:
    if m.direction == "info":
        raise ValueError("métrica informativa não pontua")
    if m.passed:
        return 1.0
    if m.direction == "range" and m.threshold_max is not None and m.score > m.threshold_max:
        bound = m.threshold_max
    else:
        bound = m.threshold
    reference = max(abs(bound), 1.0)
    return max(0.0, 1.0 - abs(m.score - bound) / reference)


def aggregate_score(report: EvaluationReport) -> float:
    scored = [metric_score(m) for m in report.metrics if m.direction != "info"]
    return round(sum(scored) / len(scored), 4) if scored else 1.0


def regressions(previous: EvaluationReport, current: EvaluationReport) -> list[str]:
    """Métricas que passavam na tentativa anterior e reprovam agora."""
    before = {m.name: m.passed for m in previous.metrics}
    return [m.name for m in current.metrics if before.get(m.name) and not m.passed]
