"""Artefatos do reflection loop: arquivo de demo e estatísticas por documento."""

import difflib
import json
from pathlib import Path

from backend.config import OUTPUTS_DIR
from backend.schemas import AttemptRecord, Audience, GraphState


def text_diff(before: str, after: str) -> list[str]:
    """Diff por frase (uma por linha), legível no terminal e no JSON."""
    return list(difflib.unified_diff(_units(before), _units(after), "antes", "depois", lineterm="", n=0))


def _units(text: str) -> list[str]:
    """Uma frase ou título por linha."""
    return [u.strip() for line in text.splitlines() for u in line.replace(". ", ".\n").splitlines() if u.strip()]


def attempt_view(h: AttemptRecord, previous: AttemptRecord | None) -> dict:
    return {
        "attempt": h.attempt,
        "aggregate_score": h.aggregate_score,
        "passed": h.report.passed,
        "metrics": [
            {"name": m.name, "score": m.score, "bound": m.bound_text(), "passed": m.passed}
            for m in h.report.metrics
        ],
        "flags": h.report.flags,
        "regressions": h.regressions,
        "injected_feedback": h.injected_feedback,
        "feedback": h.report.feedback,
        "text": h.content.plain_text(),
        "diff_from_previous": text_diff(previous.content.plain_text(), h.content.plain_text()) if previous else [],
        "tokens": {"input": h.input_tokens, "output": h.output_tokens},
        "cost_usd": h.cost_usd,
        "latency_ms": h.latency_ms,
    }


def demo_payload(state: GraphState, level: Audience, forced: bool = True, focus_cell: str | None = None) -> dict:
    """Histórico de tentativas das células de um nível.

    `forced` indica execução com --force-drift; `focus_cell` define a célula usada como exemplo.
    """
    cells = {}
    for key, history in sorted(state.history.items()):
        if not key.startswith(f"{level.value}:"):
            continue
        status = state.final_status.get(key)
        cells[key] = {
            "status": status.model_dump() if status else None,
            "attempts": [attempt_view(h, history[i - 1] if i else None) for i, h in enumerate(history)],
        }
    return {"doc_id": state.document.id, "drift_level": level.value, "forced": forced, "focus_cell": focus_cell,
            "prompts_hash": state.prompts_hash, "cells": cells}


def demo_path(doc_id: str, outputs_dir: Path = OUTPUTS_DIR) -> Path:
    return outputs_dir / "demo" / f"reflection_{doc_id}.json"


def write_demo(
    record, level: Audience, outputs_dir: Path = OUTPUTS_DIR, forced: bool = True, focus_cell: str | None = None
) -> Path:
    path = demo_path(record.doc_id, outputs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = demo_payload(record.state, level, forced=forced, focus_cell=focus_cell)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def reflection_stats(state: GraphState) -> dict:
    """% aprovação na 1ª tentativa x após o loop, tentativas médias, custo/latência extras, regressões."""
    history = state.history
    n = len(history) or 1
    first_pass = sum(h[0].report.passed for h in history.values() if h)
    final_pass = sum(s.status.startswith("aprovado") for s in state.final_status.values())
    loop_runs = [
        r for r in state.node_log
        if r.node == "refiner" or (r.node.startswith("evaluator:") and (r.attempt or 1) > 1)
    ]
    return {
        "doc_id": state.document.id,
        "cells": len(history),
        "pct_approved_first": round(100 * first_pass / n, 1),
        "pct_approved_final": round(100 * final_pass / n, 1),
        "mean_attempts": round(sum(len(h) for h in history.values()) / n, 2),
        "refined_cells": sum(len(h) > 1 for h in history.values()),
        "stagnated": sum(s.stop_reason == "estagnou" for s in state.final_status.values()),
        "regressions": sum(len(h.regressions) for hs in history.values() for h in hs),
        "extra_llm_calls": sum(1 for r in loop_runs if r.model),
        "extra_tokens": sum(r.input_tokens + r.output_tokens for r in loop_runs),
        "extra_cost_usd": round(sum(r.cost_usd for r in loop_runs), 6),
        "extra_latency_s": round(sum(r.latency_ms for r in loop_runs) / 1000, 2),
    }
