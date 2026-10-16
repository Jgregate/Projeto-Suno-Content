"""Experimento completo: manifesto, CSVs, figuras e relatório em outputs/experiment/<data>/.

    uv run python -m backend.experiments \\
        --doc <id1>+<id2> --doc <id3> --doc <id4> [--holdout <id>] \\
        --human-doc <id> [--demo-drift-doc <id>] [--data AAAA-MM-DD --retomar]

`id1+id2` une dois documentos numa fonte. O relatório é gerado apenas a partir dos CSVs.

Etapas (cada uma pode ser pulada com --skip <nome>):
  main       pipeline (com reflection) + baseline, com --force, em todos os documentos
  tradeoffs  modelo barato x forte na geração; com x sem reflection (1 documento, 1 execução nova)
  variance   avaliador N vezes sobre as mesmas saídas (1 documento; a 1ª é a avaliação da execução principal)
  human      revisao_humana.csv (cego) + avaliador_<doc>.csv para a concordância
  demo       execução com force_drift=iniciante para o cache da demo
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import random
import shutil
import statistics
import subprocess
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pandas as pd

from backend import run as run_module
from backend.config import BASELINE_PROMPTS_DIR, EVAL_PROMPTS_DIR, GLOSSARY_PATH, OUTPUTS_DIR, ROOT_DIR, THRESHOLDS_PATH, settings
from backend.evaluator.glossary import TermMatcher, load_glossary
from backend.evaluator.hybrid import HybridEvaluator
from backend.evaluator.level_classifier import predict_level
from backend.experiments.baseline import BaselineRecord, run_baseline
from backend.experiments.evaluate import evaluate_outputs
from backend.experiments.human_sheet import export as export_human_sheet
from backend.experiments.report import write_figures, write_report
from backend.graph.build import build_graph
from backend.llm import LLMClient, get_llm
from backend.prompts import prompts_hash
from backend.reflection.report import reflection_stats
from backend.run import RunRecord, merge_documents, summarize
from backend.schemas import Audience, EvaluationReport, GraphState, NodeRun, SourceDocument

log = logging.getLogger("suno")
DETERMINISTIC = ["flesch_pt", "term_density", "term_context_pct", "numeric_grounding"]
LLM_METRICS = ["claim_support", "claim_contradictions", "judge_adequacao_publico", "judge_tom", "judge_nuances", "judge_formato"]
LLMs = dict[str, LLMClient]


def sha12(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT_DIR, capture_output=True, text=True).stdout.strip()
        return out + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "sem-git"


def manifest(docs: list[SourceDocument], holdout: list[SourceDocument], llms: LLMs) -> dict:
    return {
        "date": date.today().isoformat(),
        "git_commit": git_commit(),
        "models": {role: llm.model_id for role, llm in llms.items()},
        "temperature": {"geracao": settings.llm_temperature, "avaliacao": 0.0},
        "max_attempts": settings.max_retries,
        "reflection_epsilon": settings.reflection_epsilon,
        "hashes": {
            "prompts_geracao": prompts_hash(),
            "prompts_avaliador": prompts_hash(EVAL_PROMPTS_DIR),
            "prompt_baseline": prompts_hash(BASELINE_PROMPTS_DIR),
            "thresholds": sha12(THRESHOLDS_PATH.read_bytes()),
            "glossario": sha12(GLOSSARY_PATH.read_bytes()),
        },
        "documents": [{"id": d.id, "type": d.doc_type.value, "pages": len(d.pages), "text_sha": sha12(d.text.encode()), "split": "principal"} for d in docs]
        + [{"id": d.id, "type": d.doc_type.value, "pages": len(d.pages), "text_sha": sha12(d.text.encode()), "split": "holdout"} for d in holdout],
        "python": platform.python_version(),
    }


def load_doc(spec: str) -> SourceDocument:
    """'id' ou 'id1+id2' (fonte única, ex.: os dois fatos relevantes do Bradesco)."""
    return merge_documents([run_module.load_document(i) for i in spec.split("+")])


# --- etapa main ---

def step_main(
    docs: list[SourceDocument], split: dict[str, str], llms: LLMs, exp: Path, resume: bool = False, llm_eval: bool = True
) -> pd.DataFrame:
    """Pipeline + baseline por documento. Cada documento avaliado grava um checkpoint em csv/parcial_<doc>.json.

    Com `resume`, documentos com checkpoint são lidos dele, e documentos com execução e baseline já salvos em
    runs/ e baseline/ não são gerados de novo (só a avaliação roda). Assim uma queda no meio não perde o que terminou.

    Com `llm_eval=False` (comparação determinística), pipeline e baseline são avaliados só pelas métricas
    determinísticas, sobre as execuções já salvas, sem chamar LLM; os checkpoints não são lidos nem gravados.
    """
    rows, costs, loops = [], [], []
    matcher = TermMatcher(load_glossary())
    deterministic = HybridEvaluator(matcher)  # pipeline: reaproveita os relatórios do grafo (já têm LLM)
    hybrid = HybridEvaluator(matcher, claims_llm=llms.get("claims", llms["judge"]), judge_llm=llms["judge"]) if llm_eval else deterministic
    for doc in docs:
        checkpoint = exp / "csv" / f"parcial_{doc.id}.json"
        if resume and llm_eval and checkpoint.exists():
            saved = json.loads(checkpoint.read_text(encoding="utf-8"))
            rows += saved["rows"]
            loops.append(saved["loop"])
            costs += saved["costs"]
            log.warning("retomando: %s lido do checkpoint", doc.id)
            continue
        run_file, base_file = exp / "runs" / f"{doc.id}.json", exp / "baseline" / f"{doc.id}.json"
        if resume and run_file.exists() and base_file.exists():
            record = RunRecord.model_validate_json(run_file.read_text(encoding="utf-8"))
            baseline = BaselineRecord.model_validate_json(base_file.read_text(encoding="utf-8"))
            log.warning("retomando: %s reaproveita execução e baseline salvos (só avalia)", doc.id)
        else:
            record, path, _ = run_module.run(doc, llms["fast"], llms["strong"], llms["judge"], force=True, claims=llms.get("claims"))
            shutil.copy(path, run_file)
            baseline, bpath, _ = run_baseline(doc, llms["fast"], force=True)
            shutil.copy(bpath, base_file)

        stored = record.state.reports if llm_eval else None  # determinístico: recalcula, sem os relatórios com LLM do grafo
        r, _, _, _ = evaluate_outputs(doc, "pipeline", record.state.outputs, record.state.extraction, deterministic, stored)
        # baseline avaliado pela mesma suíte; as âncoras do pipeline servem de referência factual
        rb, _, eval_runs, _ = evaluate_outputs(doc, "baseline", baseline.outputs, record.state.extraction, hybrid)
        for row in r + rb:
            row["split"] = split[doc.id]
        rows += r + rb

        stats = reflection_stats(record.state)
        stats["split"] = split[doc.id]
        loops.append(stats)
        costs.append(cost_row(doc.id, "pipeline", split[doc.id], record.state.node_log, record.totals.wall_ms))
        costs.append(cost_row(doc.id, "baseline", split[doc.id], baseline.node_log + eval_runs, None))
        node_costs(record.state.node_log, doc.id).to_csv(exp / "csv" / f"custo_por_no_{doc.id}.csv", index=False)
        if llm_eval:
            checkpoint.write_text(
                json.dumps({"rows": r + rb, "loop": stats, "costs": costs[-2:]}, ensure_ascii=False, default=str), encoding="utf-8"
            )

    df = pd.DataFrame(rows)
    df.to_csv(exp / "csv" / "metricas.csv", index=False)
    pd.DataFrame(loops).to_csv(exp / "csv" / "reflection_stats.csv", index=False)
    pd.DataFrame(costs).to_csv(exp / "csv" / "custo_por_documento.csv", index=False)
    all_nodes = pd.concat([pd.read_csv(p) for p in (exp / "csv").glob("custo_por_no_*.csv")])
    all_nodes.groupby("node", as_index=False).sum(numeric_only=True).to_csv(exp / "csv" / "custo_por_no.csv", index=False)
    return df


def cost_row(doc_id: str, system: str, split: str, runs: list[NodeRun], wall_ms: float | None) -> dict:
    calls = [r for r in runs if r.model]
    return {
        "doc_id": doc_id, "system": system, "split": split, "llm_calls": len(calls),
        "input_tokens": sum(r.input_tokens for r in calls), "output_tokens": sum(r.output_tokens for r in calls),
        "cost_usd": round(sum(r.cost_usd for r in calls), 6),
        "wall_s": round((wall_ms if wall_ms is not None else sum(r.latency_ms for r in runs)) / 1000, 2),
    }


def node_costs(runs: list[NodeRun], doc_id: str) -> pd.DataFrame:
    rows = [{"doc_id": doc_id, "node": r.node, "llm_calls": int(bool(r.model)), "input_tokens": r.input_tokens,
             "output_tokens": r.output_tokens, "cost_usd": r.cost_usd, "latency_s": r.latency_ms / 1000}
            for r in runs if r.node != "evaluator"]
    return pd.DataFrame(rows).groupby(["doc_id", "node"], as_index=False).sum(numeric_only=True)


# --- etapa variance ---

def delivered_report(state: GraphState, key: str, attempt: int | None = None) -> EvaluationReport:
    """Relatório da versão entregue da célula ou, com `attempt`, de uma tentativa específica."""
    wanted = attempt or state.outputs[key].attempt
    return next(r for r in reversed(state.reports[key]) if r.attempt == wanted)


def step_variance(doc: SourceDocument, llms: LLMs, exp: Path, repeats: int = 3) -> pd.DataFrame:
    """Avalia as mesmas saídas `repeats` vezes e mede o desvio por métrica.

    A 1ª repetição é a avaliação feita durante a execução principal (mesmas saídas, mesmo avaliador, temperatura 0);
    as demais chamam o avaliador de novo. Cada repetição nova grava csv/variancia_rep<n>.csv e é reaproveitada
    se a etapa for retomada.
    """
    record = RunRecord.model_validate_json((exp / "runs" / f"{doc.id}.json").read_text(encoding="utf-8"))
    items = sorted(record.state.outputs.items())
    rows = [{"repeticao": 1, "celula": key, "metric": m.name, "score": m.score}
            for key, _ in items for m in delivered_report(record.state, key).metrics]
    hybrid = None
    for rep in range(2, repeats + 1):
        part = exp / "csv" / f"variancia_rep{rep}.csv"
        if part.exists():
            rows += pd.read_csv(part).to_dict("records")
            continue
        hybrid = hybrid or HybridEvaluator(TermMatcher(load_glossary()), claims_llm=llms.get("claims", llms["judge"]), judge_llm=llms["judge"])
        new = [{"repeticao": rep, "celula": key, "metric": m.name, "score": m.score}
               for key, out in items for m in hybrid.evaluate(out, doc, record.state.extraction).report.metrics]
        pd.DataFrame(new).to_csv(part, index=False)
        rows += new
    long = pd.DataFrame(rows)
    long.to_csv(exp / "csv" / "variancia_bruta.csv", index=False)
    per_cell = long.groupby(["celula", "metric"]).score.agg(["mean", "std"]).reset_index()
    summary = (
        per_cell.groupby("metric")
        .agg(media=("mean", "mean"), desvio_medio_entre_repeticoes=("std", "mean"), desvio_max=("std", "max"))
        .reset_index()
    )
    summary["tipo"] = summary.metric.map(lambda m: "deterministica" if m in DETERMINISTIC else "llm")
    summary["repeticoes"] = long.repeticao.nunique()
    summary = summary.fillna(0).round(4)
    summary.to_csv(exp / "csv" / "variancia.csv", index=False)
    return summary


# --- etapa tradeoffs ---

def run_config(doc: SourceDocument, gen: LLMClient, llms: LLMs, max_attempts: int) -> tuple[GraphState, float]:
    graph = build_graph(gen, llms["strong"], judge=llms["judge"], refiner_llm=gen, max_attempts=max_attempts,
                        claims=llms.get("claims"))
    start = time.perf_counter()
    state = GraphState.model_validate(graph.invoke(GraphState(document=doc, prompts_hash=prompts_hash())))
    return state, (time.perf_counter() - start) * 1000


def first_pass(state: GraphState) -> list[NodeRun]:
    """Nós executados até a 1ª avaliação de cada célula (o que roda com max_tentativas=1)."""
    return [r for r in state.node_log if r.attempt in (None, 1)]


def first_pass_wall_ms(state: GraphState) -> float:
    """Latência de parede da 1ª passada, pelo caminho crítico: extractor, o adapter e o formatter mais lentos
    (rodam em paralelo) e a 1ª rodada do avaliador."""
    def slowest(node: str) -> float:
        return max((r.latency_ms for r in state.node_log if r.node == node), default=0.0)

    first_eval = next((r.latency_ms for r in state.node_log if r.node == "evaluator"), 0.0)
    return slowest("extractor") + slowest("adapter") + slowest("formatter") + first_eval


def config_rows(label: str, model_id: str, state: GraphState, wall_ms: float, doc_id: str) -> tuple[list[dict], list[pd.DataFrame]]:
    """Duas configurações de uma execução: com reflection (versões entregues) e sem (1ª tentativa de cada célula).
    Com max_tentativas=1 o grafo termina logo após a 1ª avaliação, então a 1ª tentativa é exatamente essa configuração."""
    rows, nodes = [], []
    variants = [
        (f"{label} + reflection", settings.max_retries, state.node_log, wall_ms, "medida",
         {k: delivered_report(state, k) for k in state.outputs},
         [s.status.startswith("aprovado") for s in state.final_status.values()],
         statistics.fmean(len(h) for h in state.history.values())),
        (f"{label} sem reflection", 1, first_pass(state), first_pass_wall_ms(state), "estimada (caminho crítico)",
         {k: delivered_report(state, k, attempt=1) for k in state.outputs},
         None, 1.0),
    ]
    for name, attempts, runs, wall, wall_kind, reports, approved, mean_attempts in variants:
        delivered = list(reports.values())
        approved = approved if approved is not None else [r.passed for r in delivered]

        def mean(metric: str, reports: list[EvaluationReport] = delivered) -> float | None:
            scores = [m.score for r in reports for m in r.metrics if m.name == metric]
            return statistics.fmean(scores) if scores else None

        t = summarize(runs, wall)
        fidelity = mean("claim_support")
        rows.append({
            "config": name, "modelo_geracao": model_id, "max_tentativas": attempts,
            "aprovacao": round(sum(approved) / len(approved), 3),
            "flesch_medio": round(mean("flesch_pt"), 2), "densidade_media": round(mean("term_density"), 2),
            "fidelidade_media": round(fidelity, 3) if fidelity is not None else None,
            "tentativas_medias": round(mean_attempts, 2),
            "chamadas_llm": t.llm_calls, "tokens": t.input_tokens + t.output_tokens, "custo_usd": t.cost_usd,
            "latencia_s": round(wall / 1000, 2), "latencia": wall_kind,
        })
        nodes.append(node_costs(runs, doc_id).assign(config=name))
    return rows, nodes


def step_tradeoffs(doc: SourceDocument, llms: LLMs, exp: Path) -> pd.DataFrame:
    """Modelo barato × forte na geração (adapters, formatters e refiner), com e sem reflection loop.

    A configuração barata é a execução principal do documento (runs/<doc>.json), que já gera com o modelo `fast`.
    A forte é uma execução nova com o modelo `strong` nesses nós, salva em tradeoffs/<doc>_forte.json para ser
    reaproveitada. A variante sem reflection de cada uma sai da 1ª tentativa da mesma execução.
    """
    main = RunRecord.model_validate_json((exp / "runs" / f"{doc.id}.json").read_text(encoding="utf-8"))
    strong_file = exp / "tradeoffs" / f"{doc.id}_forte.json"
    if strong_file.exists():
        saved = json.loads(strong_file.read_text(encoding="utf-8"))
        strong_state, strong_wall, strong_model = GraphState.model_validate(saved["state"]), saved["wall_ms"], saved["model"]
    else:
        strong_state, strong_wall = run_config(doc, llms["strong"], llms, settings.max_retries)
        strong_model = llms["strong"].model_id
        strong_file.parent.mkdir(exist_ok=True)
        strong_file.write_text(json.dumps({"model": strong_model, "wall_ms": strong_wall, "state": strong_state.model_dump(mode="json")},
                                          ensure_ascii=False), encoding="utf-8")
    rows, nodes = config_rows("barato", main.models.get("fast", llms["fast"].model_id), main.state, main.totals.wall_ms, doc.id)
    strong_rows, strong_nodes = config_rows("forte", strong_model, strong_state, strong_wall, doc.id)
    rows, nodes = rows + strong_rows, nodes + strong_nodes
    df = pd.DataFrame(rows)
    df.to_csv(exp / "csv" / "tradeoffs.csv", index=False)
    pd.concat(nodes).to_csv(exp / "csv" / "tradeoffs_por_no.csv", index=False)
    return df


# --- etapa human ---

HUMAN_COLUMNS = ["nivel_percebido", "erro_factual", "erro_descricao", "tom_1a5", "trivializou", "comentario"]


def step_human(doc: SourceDocument, exp: Path) -> None:
    """Gera o CSV de revisão humana às cegas (sem nível-alvo, notas ou status do avaliador)."""
    record = RunRecord.model_validate_json((exp / "runs" / f"{doc.id}.json").read_text(encoding="utf-8"))
    human, machine = [], []
    items = sorted(record.state.outputs.items())
    random.Random(42).shuffle(items)  # semente fixa; a ordem não revela o nível
    for i, (key, out) in enumerate(items, start=1):
        rid = f"S{i:02d}"
        human.append({"id": rid, "formato": out.format.value, "texto": out.plain_text(), **dict.fromkeys(HUMAN_COLUMNS, "")})
        report = next(r for r in reversed(record.state.reports[key]) if r.attempt == out.attempt)
        m = {x.name: x for x in report.metrics}
        machine.append({
            "id": rid, "celula": key, "nivel_alvo": out.audience.value,
            "nivel_previsto": predict_level({"flesch_pt": m["flesch_pt"].score, "term_density": m["term_density"].score}).value,
            "erro_factual": "sim" if any(not m[n].passed for n in ("numeric_grounding", "claim_support", "claim_contradictions") if n in m) else "nao",
            "judge_tom": m["judge_tom"].score if "judge_tom" in m else None,
            "trivializou": "sim" if (("term_density" in m and m["term_density"].direction in ("min", "range") and m["term_density"].score < m["term_density"].threshold)
                                     or ("judge_nuances" in m and not m["judge_nuances"].passed)) else "nao",
        })
    pd.DataFrame(human).to_csv(exp / "revisao_humana.csv", index=False)
    pd.DataFrame(machine).to_csv(exp / "csv" / f"avaliador_{doc.id}.csv", index=False)
    export_human_sheet(exp)  # mesma revisão em planilha, com listas de opção


# --- orquestração ---

def run_experiment(
    main_specs: list[str], holdout_specs: list[str], human_doc: str | None, demo_drift_doc: str | None,
    llms: LLMs, out_root: Path, skip: set[str], variance_doc: str | None = None, tradeoff_doc: str | None = None,
    run_date: str | None = None, resume: bool = False, llm_eval: bool = True, variance_repeats: int = 3,
) -> Path:
    docs = [load_doc(s) for s in main_specs]
    holdout = [load_doc(s) for s in holdout_specs]
    exp = out_root / (run_date or date.today().isoformat())  # --data reaproveita uma pasta (ex.: só a variância depois)
    for sub in ("runs", "baseline", "csv", "figuras"):
        (exp / sub).mkdir(parents=True, exist_ok=True)
    man_path = exp / "manifest.json"
    if "main" in skip and man_path.exists():  # etapa complementar: o manifesto continua sendo o da execução principal
        man = json.loads(man_path.read_text(encoding="utf-8"))
    else:
        man = manifest(docs, holdout, llms)
        man["comparacao"] = "llm" if llm_eval else "deterministica"
        man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    split = {d.id: "principal" for d in docs} | {d.id: "holdout" for d in holdout}
    by_id = {d.id: d for d in docs + holdout}

    if "main" not in skip:
        step_main(docs + holdout, split, llms, exp, resume=resume or not llm_eval, llm_eval=llm_eval)
    if "tradeoffs" not in skip and docs:
        step_tradeoffs(by_id[tradeoff_doc or docs[0].id], llms, exp)
    if "variance" not in skip and docs:
        step_variance(by_id[variance_doc or docs[0].id], llms, exp, repeats=variance_repeats)
    if "human" not in skip and human_doc:
        step_human(by_id[load_doc(human_doc).id], exp)
    if "demo" not in skip and demo_drift_doc:
        run_module.run(load_doc(demo_drift_doc), llms["fast"], llms["strong"], llms["judge"], force=True,
                       force_drift=Audience.BEGINNER, claims=llms.get("claims"))

    write_figures(exp)
    write_report(exp, man)
    return exp


def default_llms() -> LLMs:
    return {"fast": get_llm("fast"), "strong": get_llm("strong"), "judge": get_llm("judge", temperature=0),
            "claims": get_llm("claims", temperature=0)}


def main(llm_factory: Callable[[], LLMs] = default_llms) -> None:
    parser = argparse.ArgumentParser(description="Experimento final: pipeline x baseline, variância, trade-offs e relatório.")
    parser.add_argument("--doc", action="append", default=[], help="documento principal; 'id1+id2' junta dois PDFs")
    parser.add_argument("--holdout", action="append", default=[], help="documento nunca usado antes (reportado à parte)")
    parser.add_argument("--human-doc", help="documento da revisão humana (9 saídas)")
    parser.add_argument("--variance-doc", help="documento da variância (padrão: o 1º)")
    parser.add_argument("--tradeoff-doc", help="documento dos trade-offs (padrão: o 1º)")
    parser.add_argument("--repeticoes-variancia", type=int, default=3, help="avaliações por saída na variância (padrão: 3)")
    parser.add_argument("--demo-drift-doc", help="gera também a execução com desvio forçado para a demo")
    parser.add_argument("--skip", action="append", default=[], choices=["main", "variance", "tradeoffs", "human", "demo"])
    parser.add_argument("--out", type=Path, default=OUTPUTS_DIR / "experiment")
    parser.add_argument("--data", help="AAAA-MM-DD de um experimento existente, para rodar só etapas que faltaram")
    parser.add_argument("--retomar", action="store_true", help="reaproveita documentos já processados na pasta (após uma queda)")
    parser.add_argument("--comparacao-deterministica", action="store_true",
                        help="pipeline × baseline só nas métricas determinísticas, sobre execuções já salvas (sem LLM)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    exp = run_experiment(args.doc, args.holdout, args.human_doc, args.demo_drift_doc, llm_factory(), args.out, set(args.skip),
                         args.variance_doc, args.tradeoff_doc, args.data, args.retomar, not args.comparacao_deterministica,
                         args.repeticoes_variancia)
    print(f"Experimento em {exp}\nRelatório: {exp / 'relatorio_experimental.md'}")


if __name__ == "__main__":
    main()

