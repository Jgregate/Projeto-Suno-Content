"""API FastAPI para o frontend.

    uv run uvicorn backend.api.main:app --reload

Progresso por polling (GET /runs/{id}). Modo demo: sem `force`, se já existe
execução salva para o documento, ela é servida sem chamar LLM.
"""

import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend import run as run_module
from backend.api.models import (
    AgreementRow,
    AnchorOut,
    AnchorsResponse,
    BoundOut,
    CellMetrics,
    CellResult,
    CellTermsResponse,
    ConfusionMatrix,
    DocumentInfo,
    ExperimentResponse,
    GlossaryTermOut,
    LevelSummary,
    NodeCost,
    ReflectionStats,
    RunCreate,
    RunResults,
    RunState,
    RunStatus,
    StageProgress,
    SummaryResponse,
    TermOccurrenceOut,
    ThresholdsResponse,
    Totals,
    TradeoffRow,
    VarianceRow,
)
from backend.config import REPORTS_DIR
from backend.evaluator.glossary import _NLP_LOCK, TermMatcher, get_nlp, load_glossary
from backend.evaluator.hybrid import evaluation_text
from backend.evaluator.level_classifier import predict_level
from backend.evaluator.term_density import context_marker
from backend.evaluator.text import split_sentences
from backend.evaluator.thresholds import load_thresholds
from backend.ingestion.pdf import load_pdf
from backend.llm import LLMClient, get_llm
from backend.reflection.report import reflection_stats
from backend.schemas import Audience, Format, NodeRun, SourceDocument, cell_key

STAGES = {"extractor": 1, "adapters": 3, "formatters": 9, "evaluator": None, "refiner": None}
LEVELS = [a.value for a in Audience]


def default_llms() -> tuple[LLMClient, ...]:
    """Clientes (fast, strong, judge, claims). O quarto item é opcional para fábricas alternativas."""
    return get_llm("fast"), get_llm("strong"), get_llm("judge", temperature=0), get_llm("claims", temperature=0)


app = FastAPI(title="Suno Content API", version="0.4.0", description="Pipeline de adaptação calibrada de documentos financeiros.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
app.state.llm_factory = default_llms  # substituído nos testes


# --- registro de execuções (memória; resultados persistem em outputs/) ---

@dataclass
class Job:
    run_id: str
    doc_id: str
    status: RunState = "queued"
    cached: bool = False
    path: Path | None = None
    error: str | None = None
    progress: dict[str, StageProgress] = field(default_factory=lambda: {k: StageProgress(total=v) for k, v in STAGES.items()})


JOBS: dict[str, Job] = {}
_LOCK = threading.Lock()


def _stage(node: str) -> str | None:
    if node == "extractor":
        return "extractor"
    if node.startswith("adapter_"):
        return "adapters"
    if node.startswith("fmt_"):
        return "formatters"
    return node if node in ("evaluator", "refiner") else None


def _run_files(doc_id: str) -> list[Path]:
    return sorted((run_module.OUTPUTS_DIR / doc_id).glob("*.json"))


def _cached_path(doc_id: str, force_drift: Audience | None) -> Path | None:
    wanted = force_drift.value if force_drift else None
    for path in reversed(_run_files(doc_id)):
        record = run_module.RunRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if record.force_drift == wanted:
            return path
    return None


def _job(run_id: str) -> Job:
    if job := JOBS.get(run_id):
        return job
    # run_id persistente "<doc_id>__<arquivo>": serve execuções salvas mesmo após reiniciar a API
    if "__" in run_id:
        doc_id, stem = run_id.rsplit("__", 1)
        path = run_module.OUTPUTS_DIR / doc_id / f"{stem}.json"
        if path.exists():
            return Job(run_id, doc_id, "completed", cached=True, path=path)
    raise HTTPException(404, f"Execução {run_id} não encontrada.")


def _execute(job: Job, req: RunCreate) -> None:
    def progress(node: str) -> None:
        if stage := _stage(node):
            with _LOCK:
                job.progress[stage].done += 1

    job.status = "running"
    try:
        doc = run_module.load_document(req.doc_id)
        fast, strong, judge, *rest = app.state.llm_factory()
        _, path, _ = run_module.run(doc, fast, strong, judge, force=req.force, force_drift=req.force_drift, progress=progress,
                                    claims=rest[0] if rest else None)
        job.path, job.status = path, "completed"
    except Exception as exc:  # a falha fica registrada no job; a API segue respondendo
        job.status, job.error = "failed", f"{type(exc).__name__}: {exc}"


# --- documentos ---

def _doc_info(doc: SourceDocument) -> DocumentInfo:
    return DocumentInfo(id=doc.id, title=doc.title, doc_type=doc.doc_type, date=doc.date,
                        pages=len(doc.pages), runs=len(_run_files(doc.id)))


@app.post("/documents", response_model=DocumentInfo, status_code=201, tags=["documents"])
async def upload_document(file: Annotated[UploadFile, File()]) -> DocumentInfo:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Envie um arquivo .pdf")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(file.filename).stem).strip("-") or "documento"
    run_module.RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw = run_module.RAW_DIR / f"{stem}.pdf"
    raw.write_bytes(await file.read())
    try:
        doc = load_pdf(raw)
    except Exception as exc:
        raise HTTPException(422, f"Não foi possível ler o PDF: {exc}") from exc
    run_module.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (run_module.PROCESSED_DIR / f"{doc.id}.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    return _doc_info(doc)


@app.get("/documents", response_model=list[DocumentInfo], tags=["documents"])
def list_documents() -> list[DocumentInfo]:
    """Documentos processados e fontes compostas que já têm execução salva.

    Documentos que integram uma fonte composta não são listados isoladamente.
    """
    processed = {p.stem: p for p in sorted(run_module.PROCESSED_DIR.glob("*.json"))}
    root = run_module.OUTPUTS_DIR
    merged = sorted(
        d.name for d in (root.iterdir() if root.exists() else [])
        if d.is_dir() and "__" in d.name and all(part in processed for part in d.name.split("__")) and _run_files(d.name)
    )
    parts = {part for name in merged for part in name.split("__")}
    docs = [run_module.load_document(name) for name in merged]
    docs += [SourceDocument.model_validate_json(p.read_text(encoding="utf-8")) for stem, p in processed.items() if stem not in parts]
    return sorted((_doc_info(d) for d in docs), key=lambda d: (-d.runs, d.id))


@app.get("/documents/{doc_id}/anchors", response_model=AnchorsResponse, tags=["documents"])
def document_anchors(doc_id: str) -> AnchorsResponse:
    files = _run_files(doc_id)
    if not files:
        raise HTTPException(404, f"Sem execução para {doc_id}; as âncoras saem do extractor.")
    path = _cached_path(doc_id, None) or files[-1]  # execução normal, não a de demonstração (force_drift)
    record = run_module.RunRecord.model_validate_json(path.read_text(encoding="utf-8"))
    state = record.state
    source_by_page = {p.number: p.source_doc_id for p in state.document.pages}
    anchors = [
        AnchorOut(**a.model_dump(), source_doc_id=source_by_page.get(a.page))
        for a in (state.extraction.anchors if state.extraction else [])
    ]
    return AnchorsResponse(doc_id=doc_id, run_id=f"{doc_id}__{path.stem}", anchors=anchors)


# --- execuções ---

@app.post("/runs", response_model=RunStatus, status_code=202, tags=["runs"])
def create_run(req: RunCreate, background: BackgroundTasks) -> RunStatus:
    try:
        run_module.load_document(req.doc_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

    if not req.force and (path := _cached_path(req.doc_id, req.force_drift)):
        job = Job(f"{req.doc_id}__{path.stem}", req.doc_id, "completed", cached=True, path=path)
        for p in job.progress.values():
            p.done = p.total or 0
    else:
        job = Job(uuid.uuid4().hex, req.doc_id)
        background.add_task(_execute, job, req)
    JOBS[job.run_id] = job
    return run_status(job.run_id)


@app.get("/runs/{run_id}", response_model=RunStatus, tags=["runs"])
def run_status(run_id: str) -> RunStatus:
    job = _job(run_id)
    return RunStatus(run_id=job.run_id, doc_id=job.doc_id, status=job.status, cached=job.cached,
                     progress=job.progress, error=job.error)


def node_costs(runs: list[NodeRun]) -> list[NodeCost]:
    """Telemetria agregada por nó (o registro "evaluator" é o tempo real do nó e fica de fora)."""
    groups: dict[str, list[NodeRun]] = {}
    for r in runs:
        if r.node != "evaluator":
            groups.setdefault(r.node, []).append(r)
    return [
        NodeCost(node=node, calls=len(rs), llm_calls=sum(1 for r in rs if r.model),
                 input_tokens=sum(r.input_tokens for r in rs), output_tokens=sum(r.output_tokens for r in rs),
                 cost_usd=round(sum(r.cost_usd for r in rs), 6), latency_ms=round(sum(r.latency_ms for r in rs), 1))
        for node, rs in sorted(groups.items())
    ]


def _totals(t) -> Totals | None:
    return Totals(**t.model_dump(include=set(Totals.model_fields))) if t else None


@app.get("/runs/{run_id}/results", response_model=RunResults, tags=["runs"])
def run_results(run_id: str) -> RunResults:
    job = _job(run_id)
    if job.status != "completed" or not job.path:
        raise HTTPException(409, f"Execução {run_id} ainda não terminou ({job.status}).")
    record = run_module.RunRecord.model_validate_json(job.path.read_text(encoding="utf-8"))
    state = record.state
    cells = []
    for audience in Audience:
        for fmt in Format:
            key = cell_key(audience, fmt)
            if key not in state.outputs:
                continue
            out = state.outputs[key]
            report = next((r for r in reversed(state.reports.get(key, [])) if r.attempt == out.attempt), None)
            cells.append(CellResult(audience=audience, format=fmt, status=state.final_status.get(key), content=out,
                                    report=report, history=state.history.get(key, [])))
    return RunResults(
        run_id=job.run_id, doc_id=record.doc_id, created_at=record.created_at, prompts_hash=record.prompts_hash,
        models=record.models, force_drift=record.force_drift, cells=cells, adapted=state.adapted,
        generation=_totals(record.generation), evaluation=_totals(record.evaluation), warnings=state.warnings,
        node_costs=node_costs(state.node_log),
    )


# --- relatórios ---

def _latest_metrics_csv(root: Path) -> Path | None:
    """metricas.csv mais recente: outputs/reports/ (backend.experiments.evaluate) ou outputs/experiment/<data>/csv/."""
    candidates = [REPORTS_DIR / "metricas.csv", *root.glob("experiment/*/csv/metricas.csv")]
    existing = [p for p in candidates if p.exists()]
    return max(existing, key=lambda p: p.stat().st_mtime) if existing else None


@app.get("/reports/summary", response_model=SummaryResponse, tags=["reports"])
def reports_summary() -> SummaryResponse:
    import pandas as pd

    rows, reflection, docs, cells, all_runs = [], [], [], [], []
    root = run_module.OUTPUTS_DIR
    csv = _latest_metrics_csv(root) if root.exists() else None
    exp_runs = csv.parent.parent / "runs" if csv is not None else None
    doc_dirs = sorted(p for p in root.iterdir() if p.is_dir() and p.name not in {"reports", "demo", "experiment"}) if root.exists() else []
    for doc_dir in doc_dirs:
        # documentos do experimento usam a execução dele, para o resumo bater com o baseline e o relatório
        # (gerações posteriores aparecem na matriz do documento); os demais, a última execução normal
        # (force_drift é demonstração e não entra no resumo)
        official = exp_runs / f"{doc_dir.name}.json" if exp_runs is not None else None
        path = official if official is not None and official.exists() else _cached_path(doc_dir.name, None)
        if path is None:
            continue
        state = run_module.RunRecord.model_validate_json(path.read_text(encoding="utf-8")).state
        docs.append(state.document.id)
        reflection.append(ReflectionStats(**reflection_stats(state)))
        all_runs += state.node_log
        for key, out in state.outputs.items():
            report = next((r for r in reversed(state.reports.get(key, [])) if r.attempt == out.attempt), None)
            if not report:
                continue
            flesch, density = report.metric("flesch_pt"), report.metric("term_density")
            status = state.final_status.get(key)
            cells.append(CellMetrics(
                system="pipeline", doc_id=state.document.id, audience=out.audience, format=out.format,
                passed=status.status.startswith("aprovado") if status else report.passed,
                predicted_level=predict_level({"flesch_pt": flesch.score, "term_density": density.score}) if flesch and density else None,
                metrics={m.name: m.score for m in report.metrics},
            ))
            rows.append({
                "system": "pipeline", "audience": out.audience.value,
                "passed": status.status.startswith("aprovado") if status else report.passed,
                "flesch_pt": flesch.score if flesch else None, "term_density": density.score if density else None,
                "predicted_level": predict_level({"flesch_pt": flesch.score, "term_density": density.score}).value
                if flesch and density else None,
            })

    notes = []
    if csv is not None:
        base = pd.read_csv(csv)
        manifest = csv.parent.parent / "manifest.json"
        deterministic = manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")).get("comparacao") == "deterministica"
        if deterministic and (base.system == "pipeline").any():
            # comparação determinística: pipeline e baseline vêm do mesmo CSV
            rows = [r for r in rows if r["system"] != "pipeline"]
            rows += base[base.system == "pipeline"][["system", "audience", "passed", "flesch_pt", "term_density", "predicted_level"]].to_dict("records")
            notes.append("Pipeline × baseline comparados só nas métricas determinísticas (legibilidade, densidade, contextualização e "
                         "grounding), recalculadas para os dois sistemas. O reflection loop usou o avaliador completo.")
        baseline = base[base.system == "baseline"]
        rows += baseline[["system", "audience", "passed", "flesch_pt", "term_density", "predicted_level"]].to_dict("records")
        metric_cols = [c for c in baseline.columns if f"{c}_ok" in baseline.columns]
        for rec in baseline.to_dict("records"):
            cells.append(CellMetrics(
                system="baseline", doc_id=rec["doc_id"], audience=rec["audience"], format=rec["format"],
                passed=bool(rec["passed"]), predicted_level=rec["predicted_level"],
                metrics={c: float(rec[c]) for c in metric_cols if pd.notna(rec[c])},
            ))
    else:
        notes.append("Baseline ausente: rode backend.experiments (ou backend.experiments.baseline + backend.experiments.evaluate).")
    if not rows:
        notes.append("Nenhuma execução em outputs/.")
        return SummaryResponse(documents=docs, levels=[], confusion={}, pass_rate_by_system={}, reflection=reflection,
                               notes=notes, cells=cells, node_costs=node_costs(all_runs))

    df = pd.DataFrame(rows)
    levels = [
        LevelSummary(system=s, audience=Audience(a), cells=len(g), pass_rate=round(float(g.passed.mean()), 3),
                     flesch_mean=round(float(g.flesch_pt.mean()), 2) if g.flesch_pt.notna().any() else None,
                     density_mean=round(float(g.term_density.mean()), 2) if g.term_density.notna().any() else None)
        for (s, a), g in df.groupby(["system", "audience"])
    ]
    confusion = {}
    for system, g in df.dropna(subset=["predicted_level"]).groupby("system"):
        matrix = [[int(((g.audience == t) & (g.predicted_level == p)).sum()) for p in LEVELS] for t in LEVELS]
        confusion[system] = ConfusionMatrix(labels=LEVELS, matrix=matrix)
    pass_rate = {s: round(float(g.passed.mean()), 3) for s, g in df.groupby("system")}
    return SummaryResponse(documents=docs, levels=levels, confusion=confusion, pass_rate_by_system=pass_rate,
                           reflection=reflection, notes=notes, cells=cells, node_costs=node_costs(all_runs))


@app.get("/reports/experiment", response_model=ExperimentResponse, tags=["reports"])
def reports_experiment() -> ExperimentResponse:
    """Variância do avaliador, trade-offs e concordância humana do experimento mais recente (CSVs em csv/)."""
    import pandas as pd

    root = run_module.OUTPUTS_DIR
    metrics = _latest_metrics_csv(root) if root.exists() else None
    if metrics is None:
        return ExperimentResponse()
    csv_dir = metrics.parent
    manifest = csv_dir.parent / "manifest.json"

    def rows(name: str) -> list[dict]:
        path = csv_dir / name
        if not path.exists():
            return []
        df = pd.read_csv(path)
        return df.astype(object).where(df.notna(), None).to_dict("records")  # NaN -> None

    var = rows("variancia.csv")
    return ExperimentResponse(
        date=json.loads(manifest.read_text(encoding="utf-8"))["date"] if manifest.exists() else None,
        repeats=int(var[0]["repeticoes"]) if var and var[0].get("repeticoes") is not None else None,
        variance=[VarianceRow(metric=r["metric"], tipo=r["tipo"], media=r["media"], desvio_medio=r["desvio_medio_entre_repeticoes"],
                              desvio_max=r["desvio_max"]) for r in var],
        tradeoffs=[TradeoffRow(**{k: v for k, v in r.items() if k in TradeoffRow.model_fields},
                               latencia_estimada=str(r.get("latencia") or "").startswith("estimada")) for r in rows("tradeoffs.csv")],
        agreement=[AgreementRow(dimensao=r["dimensao"], n=int(r["n"] or 0), concordancia=r["concordancia"], ic95_inf=r["ic95_inf"],
                                ic95_sup=r["ic95_sup"], kappa=r["kappa_cohen"]) for r in rows("concordancia.csv")],
    )


# --- glossário, termos por célula e limiares ---

_MATCHER: TermMatcher | None = None


def _matcher() -> TermMatcher:
    global _MATCHER
    if _MATCHER is None:
        _MATCHER = TermMatcher(load_glossary())
    return _MATCHER


@app.get("/glossary", response_model=list[GlossaryTermOut], tags=["reference"])
def glossary() -> list[GlossaryTermOut]:
    return [GlossaryTermOut(**t.model_dump()) for t in load_glossary().termos]


@app.get("/thresholds", response_model=ThresholdsResponse, tags=["reference"])
def thresholds() -> ThresholdsResponse:
    raw = load_thresholds().raw
    to_bounds = lambda d: {k: BoundOut(**(v or {})) for k, v in d.items()}
    return ThresholdsResponse(levels={lvl: to_bounds(m) for lvl, m in raw["levels"].items()}, common=to_bounds(raw["common"]))


@app.get("/runs/{run_id}/cells/{audience}/{fmt}/terms", response_model=CellTermsResponse, tags=["runs"])
def cell_terms(run_id: str, audience: Audience, fmt: Format, attempt: int | None = None) -> CellTermsResponse:
    """Ocorrências de termos do glossário na célula, com o trecho exato e a contextualização.

    Usa `context_marker`, a mesma regra da métrica `term_context_pct`.
    """
    job = _job(run_id)
    if job.status != "completed" or not job.path:
        raise HTTPException(409, f"Execução {run_id} ainda não terminou ({job.status}).")
    state = run_module.RunRecord.model_validate_json(job.path.read_text(encoding="utf-8")).state
    key = cell_key(audience, fmt)
    if key not in state.outputs:
        raise HTTPException(404, f"Célula {key} não existe nesta execução.")
    content = state.outputs[key]
    if attempt is not None:
        content = next((h.content for h in state.history.get(key, []) if h.attempt == attempt), None)
        if content is None:
            raise HTTPException(404, f"Tentativa {attempt} não existe para {key}.")

    matcher = _matcher()
    sentences = split_sentences(evaluation_text(content))
    occurrences = []
    for i, sentence in enumerate(sentences):
        with _NLP_LOCK:
            tokens = [t for t in get_nlp()(sentence) if not t.is_space]
        for match in matcher.find(sentence):
            first, last = tokens[match.start], tokens[match.end - 1]
            term = matcher.glossary.get(match.termo)
            needs = term.needs_explanation_for(audience)
            marker = context_marker(sentences, i) if needs else None
            occurrences.append(TermOccurrenceOut(
                termo=term.termo, surface=sentence[first.idx: last.idx + len(last.text)], sentence_index=i,
                sentence=sentence, needs_context=needs, marker=marker, contextualized=not needs or marker is not None,
            ))
    return CellTermsResponse(run_id=run_id, audience=audience, format=fmt, attempt=content.attempt, occurrences=occurrences)
