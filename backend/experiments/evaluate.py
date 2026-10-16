"""Avalia pipeline e baseline com a mesma suíte e gera os relatórios.

Uso:
    uv run python -m backend.experiments.evaluate              # só métricas determinísticas no que faltar
    uv run python -m backend.experiments.evaluate --llm        # inclui fidelidade por afirmações e judge
    uv run python -m backend.experiments.evaluate --doc <id>   # restringe a documentos

Para o pipeline, relatórios já gravados pelo grafo (com LLM) são reaproveitados;
a parte determinística é recalculada (é idêntica, por construção) para preencher
as colunas extras. Saídas em outputs/reports/:
    metricas.csv               uma linha por documento x sistema x célula
    matriz_confusao_<sis>.csv  nível alvo x nível previsto (+ .png)
    reprovadas.md              células reprovadas com o feedback gerado
    custo_avaliador.csv        custo e latência do avaliador por documento e sistema
    reflection_stats.csv       aprovação 1ª tentativa x pós-loop, tentativas, custo extra, regressões
"""

import argparse
import time
from pathlib import Path

import pandas as pd

from backend.config import OUTPUTS_DIR, REPORTS_DIR
from backend.evaluator.glossary import TermMatcher, load_glossary
from backend.evaluator.hybrid import HybridEvaluator
from backend.evaluator.readability import textstat_flesch_pt
from backend.experiments.baseline import latest_baseline
from backend.llm import get_llm
from backend.reflection.report import reflection_stats
from backend.run import RunRecord, load_document
from backend.schemas import Audience, EvaluationReport, ExtractionResult, GeneratedContent, NodeRun, SourceDocument

LEVELS = [a.value for a in Audience]


def latest_run(doc_id: str) -> RunRecord | None:
    files = sorted((OUTPUTS_DIR / doc_id).glob("*.json"))
    return RunRecord.model_validate_json(files[-1].read_text(encoding="utf-8")) if files else None


def _row(doc_id: str, system: str, out: GeneratedContent, ev, report: EvaluationReport) -> dict:
    row = {
        "doc_id": doc_id, "system": system, "audience": out.audience.value, "format": out.format.value,
        "attempt": out.attempt, "passed": report.passed, "predicted_level": ev.predicted_level.value,
        "flags": ";".join(report.flags), "words": ev.readability.words,
        "words_per_sentence": ev.readability.words_per_sentence,
        "syllables_per_word": ev.readability.syllables_per_word,
        "pct_polysyllables": ev.readability.pct_polysyllables,
        "flesch_textstat": textstat_flesch_pt(out.plain_text()),
    }
    for m in report.metrics:
        row[m.name] = m.score
        row[f"{m.name}_ok"] = m.passed
    return row


def evaluate_outputs(
    doc: SourceDocument,
    system: str,
    outputs: dict[str, GeneratedContent],
    extraction: ExtractionResult | None,
    hybrid: HybridEvaluator,
    stored: dict[str, list[EvaluationReport]] | None = None,
) -> tuple[list[dict], list[dict], list[NodeRun], float]:
    rows, failed, runs = [], [], []
    start = time.perf_counter()
    for key, out in sorted(outputs.items()):
        # a saída entregue pode ser uma tentativa anterior (melhor nota); procura o relatório dela
        previous = [r for r in (stored or {}).get(key, []) if r.attempt == out.attempt]
        reuse = previous[-1] if previous and hybrid.judge_llm is None else None
        ev = hybrid.evaluate(out, doc, extraction)
        report = reuse or ev.report
        runs += [] if reuse else ev.runs
        rows.append(_row(doc.id, system, out, ev, report))
        if not report.passed:
            failed.append({"doc_id": doc.id, "system": system, "cell": key, "feedback": report.feedback,
                           "failed": ", ".join(m.name for m in report.failed_metrics)})
    return rows, failed, runs, (time.perf_counter() - start) * 1000


def confusion(df: pd.DataFrame, system: str, out_dir: Path) -> pd.DataFrame:
    sub = df[df.system == system]
    matrix = pd.crosstab(
        pd.Categorical(sub.audience, LEVELS), pd.Categorical(sub.predicted_level, LEVELS),
        rownames=["alvo"], colnames=["previsto"], dropna=False,
    )
    matrix.to_csv(out_dir / f"matriz_confusao_{system}.csv")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4.8, 4))
    ax.imshow(matrix.values, cmap="Blues")
    ax.set_xticks(range(3), LEVELS)
    ax.set_yticks(range(3), LEVELS)
    ax.set_xlabel("nível previsto pelas métricas")
    ax.set_ylabel("nível alvo")
    acc = (sub.audience == sub.predicted_level).mean() if len(sub) else 0
    ax.set_title(f"{system}: {acc:.0%} no nível certo (n={len(sub)})")
    for i in range(3):
        for j in range(3):
            ax.text(j, i, int(matrix.values[i, j]), ha="center", va="center")
    fig.tight_layout()
    fig.savefig(out_dir / f"matriz_confusao_{system}.png", dpi=150)
    plt.close(fig)
    return matrix


def cost_row(doc_id: str, system: str, runs: list[NodeRun], wall_ms: float) -> dict:
    calls = [r for r in runs if r.model]
    return {"doc_id": doc_id, "system": system, "llm_calls": len(calls),
            "input_tokens": sum(r.input_tokens for r in calls), "output_tokens": sum(r.output_tokens for r in calls),
            "cost_usd": round(sum(r.cost_usd for r in calls), 6), "wall_s": round(wall_ms / 1000, 2)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia pipeline x baseline e gera os relatórios.")
    parser.add_argument("--doc", action="append")
    parser.add_argument("--llm", action="store_true", help="roda fidelidade por afirmações e judge onde faltar")
    args = parser.parse_args()

    doc_ids = args.doc or sorted(p.name for p in OUTPUTS_DIR.iterdir() if p.is_dir() and p.name not in {"reports", "demo"})
    if not doc_ids:
        raise SystemExit("Nenhuma execução em outputs/. Rode antes backend.run e backend.experiments.baseline.")

    judge_llm = get_llm("judge", temperature=0) if args.llm else None
    claims_llm = get_llm("claims", temperature=0) if args.llm else None
    hybrid = HybridEvaluator(TermMatcher(load_glossary()), claims_llm=claims_llm, judge_llm=judge_llm)
    rows, failed, costs, loop_stats = [], [], [], []
    for doc_id in doc_ids:
        run = latest_run(doc_id)
        doc = run.state.document if run else load_document(doc_id)
        extraction = run.state.extraction if run else None
        if run:
            loop_stats.append(reflection_stats(run.state))
            r, f, runs, wall = evaluate_outputs(doc, "pipeline", run.state.outputs, extraction, hybrid, run.state.reports)
            rows += r
            failed += f
            graph_eval = [n for n in run.state.node_log if n.node.startswith("evaluator")]
            graph_wall = sum(n.latency_ms for n in graph_eval if n.node == "evaluator")
            costs.append(cost_row(doc_id, "pipeline", graph_eval + runs, graph_wall + (wall if runs else 0)))
        if baseline := latest_baseline(doc_id):
            r, f, runs, wall = evaluate_outputs(doc, "baseline", baseline.outputs, extraction, hybrid)
            rows += r
            failed += f
            costs.append(cost_row(doc_id, "baseline", runs, wall))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(REPORTS_DIR / "metricas.csv", index=False)
    pd.DataFrame(costs).to_csv(REPORTS_DIR / "custo_avaliador.csv", index=False)
    if loop_stats:
        stats = pd.DataFrame(loop_stats)
        stats.to_csv(REPORTS_DIR / "reflection_stats.csv", index=False)
        print(f"\nReflection loop:\n{stats.to_string(index=False)}")
    for system in df.system.unique():
        print(f"\nMatriz de confusão ({system}):\n{confusion(df, system, REPORTS_DIR)}")
    lines = ["# Saídas reprovadas e feedback\n"]
    for f in failed:
        lines += [f"## {f['system']} · {f['doc_id']} · {f['cell']}", f"Métricas reprovadas: {f['failed']}", "", f["feedback"], ""]
    (REPORTS_DIR / "reprovadas.md").write_text("\n".join(lines), encoding="utf-8")

    summary = df.groupby("system").agg(celulas=("passed", "size"), aprovadas=("passed", "sum"))
    print(f"\n{summary}\n\nRelatórios em {REPORTS_DIR}")


if __name__ == "__main__":
    main()
