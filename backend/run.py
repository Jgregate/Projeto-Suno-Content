"""Executa o grafo para um documento e salva em outputs/<doc_id>/<timestamp>.json.

Uso:
    uv run python -m backend.run --doc ata-copom-2026-09-16
    uv run python -m backend.run --doc <id1> --doc <id2>    # une os documentos numa fonte
    uv run python -m backend.run --doc <id> --force           # ignora o cache

Cache: reutiliza a execução mais recente com o mesmo documento, prompts, glossário,
prompts do avaliador, limiares e modelos.
"""

import argparse
import hashlib
import json
import logging
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from backend.config import EVAL_PROMPTS_DIR, GLOSSARY_PATH, OUTPUTS_DIR, PROCESSED_DIR, RAW_DIR, THRESHOLDS_PATH
from backend.graph.build import build_graph
from backend.ingestion.pdf import load_pdf
from backend.llm import LLMClient, get_llm
from backend.prompts import prompts_hash
from backend.schemas import Audience, GraphState, NodeRun, Page, SourceDocument

log = logging.getLogger("suno")


class RunTotals(BaseModel):
    llm_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    wall_ms: float = Field(description="Tempo real (nós paralelos se sobrepõem).")
    sum_node_ms: float = Field(description="Soma das latências dos nós.")


def is_eval_run(run: NodeRun) -> bool:
    return run.node.startswith("evaluator")


def summarize(runs: list[NodeRun], wall_ms: float) -> RunTotals:
    calls = [r for r in runs if r.model]
    return RunTotals(
        llm_calls=len(calls),
        input_tokens=sum(r.input_tokens for r in calls),
        output_tokens=sum(r.output_tokens for r in calls),
        cost_usd=round(sum(r.cost_usd for r in calls), 6),
        wall_ms=round(wall_ms, 1),
        sum_node_ms=round(sum(r.latency_ms for r in runs if r.node != "evaluator"), 1),
    )


class RunRecord(BaseModel):
    doc_id: str
    prompts_hash: str
    glossary_hash: str
    eval_hash: str = ""
    force_drift: str | None = None
    models: dict[str, str]
    created_at: str
    totals: RunTotals
    generation: RunTotals | None = None
    evaluation: RunTotals | None = None
    state: GraphState


def load_document(doc_id: str) -> SourceDocument:
    """Carrega data/processed/<id>.json, ingerindo data/raw/<id>.pdf se necessário.

    Ids compostos ("<id1>__<id2>", gerados por `merge_documents`) são remontados a partir das partes.
    """
    processed = PROCESSED_DIR / f"{doc_id}.json"
    if not processed.exists() and "__" in doc_id:
        return merge_documents([load_document(part) for part in doc_id.split("__")])
    if processed.exists():
        return SourceDocument.model_validate_json(processed.read_text(encoding="utf-8"))
    raw = RAW_DIR / f"{doc_id}.pdf"
    if not raw.exists():
        raise FileNotFoundError(f"Nem {processed} nem {raw} existem.")
    doc = load_pdf(raw)
    processed.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    return doc


def merge_documents(docs: list[SourceDocument]) -> SourceDocument:
    """Junta vários documentos numa fonte única, na ordem dada."""
    if len(docs) == 1:
        return docs[0]
    pages = [
        Page(number=i, text=p.text, source_doc_id=d.id)
        for i, (d, p) in enumerate(((d, p) for d in docs for p in d.pages), start=1)
    ]
    return SourceDocument(
        id="__".join(d.id for d in docs),
        doc_type=docs[0].doc_type,
        title=" + ".join(d.title for d in docs),
        date=max((d.date for d in docs if d.date), default=None),
        text="\n\n".join(p.text for p in pages),
        pages=pages,
    )


def glossary_hash() -> str:
    """O glossário entra nos prompts dos adaptadores, então também invalida o cache."""
    return hashlib.sha256(GLOSSARY_PATH.read_bytes()).hexdigest()[:12]


def eval_hash() -> str:
    """Prompts do avaliador + limiares: mudar qualquer um invalida o cache."""
    return hashlib.sha256((prompts_hash(EVAL_PROMPTS_DIR) + THRESHOLDS_PATH.read_text(encoding="utf-8")).encode()).hexdigest()[:12]


def find_cached(doc_id: str, key: dict) -> Path | None:
    for path in sorted((OUTPUTS_DIR / doc_id).glob("*.json"), reverse=True):
        meta = json.loads(path.read_text(encoding="utf-8"))
        if all(meta.get(k) == v for k, v in key.items()):
            return path
    return None


def run(
    doc: SourceDocument,
    fast: LLMClient,
    strong: LLMClient,
    judge: LLMClient | None = None,
    force: bool = False,
    use_llm_eval: bool = True,
    force_drift: Audience | None = None,
    progress: Callable[[str], None] | None = None,
    claims: LLMClient | None = None,
) -> tuple[RunRecord, Path, bool]:
    """Roda (ou reaproveita) o pipeline. Devolve (registro, caminho, veio_do_cache).

    `progress` recebe o nome de cada nó concluído. `force_drift` gera o nível indicado com as
    regras do Avançado na 1ª tentativa.
    """
    phash = prompts_hash()
    judge = judge or strong
    claims = claims or judge
    models = {"fast": fast.model_id, "strong": strong.model_id, "judge": judge.model_id if use_llm_eval else "off"}
    if use_llm_eval and claims is not judge:
        models["claims"] = claims.model_id
    key = {
        "prompts_hash": phash, "glossary_hash": glossary_hash(), "eval_hash": eval_hash(), "models": models,
        "force_drift": force_drift.value if force_drift else None,
    }
    if not force and (cached := find_cached(doc.id, key)):
        return RunRecord.model_validate_json(cached.read_text(encoding="utf-8")), cached, True

    graph = build_graph(fast, strong, judge=judge, use_llm_eval=use_llm_eval, claims=claims)
    start = time.perf_counter()
    final = None
    initial = GraphState(document=doc, prompts_hash=phash, force_drift=force_drift)
    for mode, chunk in graph.stream(initial, stream_mode=["updates", "values"]):
        if mode == "updates" and progress:
            for node in chunk:
                progress(node)
        elif mode == "values":
            final = chunk
    wall_ms = (time.perf_counter() - start) * 1000
    state = GraphState.model_validate(final)

    eval_runs = [r for r in state.node_log if is_eval_run(r)]
    eval_wall = sum(r.latency_ms for r in eval_runs if r.node == "evaluator")
    record = RunRecord(
        doc_id=doc.id,
        prompts_hash=phash,
        glossary_hash=key["glossary_hash"],
        eval_hash=key["eval_hash"],
        force_drift=key["force_drift"],
        models=models,
        created_at=datetime.now().isoformat(timespec="seconds"),
        totals=summarize(state.node_log, wall_ms),
        generation=summarize([r for r in state.node_log if not is_eval_run(r)], wall_ms - eval_wall),
        evaluation=summarize(eval_runs, eval_wall),
        state=state,
    )
    out_dir = OUTPUTS_DIR / doc.id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{datetime.now():%Y%m%d-%H%M%S-%f}.json"
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    if force_drift:
        from backend.reflection.report import write_demo

        write_demo(record, force_drift, OUTPUTS_DIR)
    return record, path, False


def main() -> None:
    parser = argparse.ArgumentParser(description="Roda o pipeline Suno Content para um documento.")
    parser.add_argument("--doc", action="append", required=True, help="id do documento (repita para juntar)")
    parser.add_argument("--force", action="store_true", help="ignora o cache")
    parser.add_argument("--no-llm-eval", action="store_true", help="avaliador só determinístico")
    parser.add_argument("--force-drift", choices=[a.value for a in Audience], help="demo: gera o nível com regras do Avançado")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    doc = merge_documents([load_document(d) for d in args.doc])
    use_llm = not args.no_llm_eval
    judge = get_llm("judge", temperature=0) if use_llm else None
    claims = get_llm("claims", temperature=0) if use_llm else None
    drift = Audience(args.force_drift) if args.force_drift else None
    record, path, cached = run(
        doc, get_llm("fast"), get_llm("strong"), judge, force=args.force, use_llm_eval=use_llm, force_drift=drift, claims=claims
    )
    print(f"{'[cache] ' if cached else ''}{path}")
    for label, t in [("geração", record.generation), ("avaliação", record.evaluation)]:
        if t:
            print(
                f"{label}: {t.llm_calls} chamadas | {t.input_tokens:,} in + {t.output_tokens:,} out | "
                f"US$ {t.cost_usd:.4f} | {t.wall_ms / 1000:.1f}s"
            )
    reports = record.state.reports
    approved = sum(s.status.startswith("aprovado") for s in record.state.final_status.values())
    print(f"saídas: {len(record.state.outputs)}/9 | aprovadas: {approved}/{len(reports)} | avisos: {len(record.state.warnings)}")
    for key, status in sorted(record.state.final_status.items()):
        print(f"  {key:<24} {status.status:<18} tentativas={status.attempts} entregue={status.delivered_attempt}")
    if drift:
        print(f"demo: outputs/demo/reflection_{doc.id}.json  ->  uv run python -m backend.reflection.show --doc {doc.id}")


if __name__ == "__main__":
    main()
