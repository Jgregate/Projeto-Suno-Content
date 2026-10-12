"""Modelos de resposta da API. Também definem o `openapi.json` usado pelo frontend."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from backend.schemas import (
    AdaptedContent,
    AttemptRecord,
    Audience,
    CellStatus,
    DocumentType,
    EvaluationReport,
    Format,
    GeneratedContent,
)


class DocumentInfo(BaseModel):
    id: str
    title: str
    doc_type: DocumentType
    date: dt.date | None
    pages: int
    runs: int = Field(description="Execuções salvas para o documento.")


class RunCreate(BaseModel):
    doc_id: str
    force: bool = Field(default=False, description="Ignora o cache e chama o LLM.")
    force_drift: Audience | None = Field(default=None, description="Demo do reflection loop.")


RunState = Literal["queued", "running", "completed", "failed"]


class StageProgress(BaseModel):
    done: int = 0
    total: int | None = Field(default=None, description="None quando o total depende do loop (avaliador/refiner).")


class RunStatus(BaseModel):
    run_id: str
    doc_id: str
    status: RunState
    cached: bool = Field(description="Servido do cache, sem chamar LLM.")
    progress: dict[str, StageProgress]
    error: str | None = None


class CellResult(BaseModel):
    audience: Audience
    format: Format
    status: CellStatus | None
    content: GeneratedContent = Field(description="Versão entregue (aprovada ou a de melhor nota).")
    report: EvaluationReport | None = Field(description="Relatório da versão entregue.")
    history: list[AttemptRecord] = Field(description="Todas as tentativas, em ordem.")


class Totals(BaseModel):
    llm_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    wall_ms: float


class RunResults(BaseModel):
    run_id: str
    doc_id: str
    created_at: str
    prompts_hash: str
    models: dict[str, str]
    force_drift: str | None
    cells: list[CellResult] = Field(description="Matriz 3x3, ordenada por nível e formato.")
    adapted: dict[str, AdaptedContent] = Field(description="Afirmações por nível com os ids das âncoras que as sustentam.")
    generation: Totals | None
    evaluation: Totals | None
    warnings: list[str]
    node_costs: list["NodeCost"] = Field(default_factory=list)


class AnchorOut(BaseModel):
    id: str
    claim: str
    numbers: list[str]
    source_excerpt: str
    page: int
    source_doc_id: str | None = Field(description="PDF de origem quando a fonte junta vários documentos.")
    valid: bool
    invalid_numbers: list[str]


class AnchorsResponse(BaseModel):
    doc_id: str
    run_id: str
    anchors: list[AnchorOut]


class LevelSummary(BaseModel):
    system: str
    audience: Audience
    cells: int
    pass_rate: float
    flesch_mean: float | None
    density_mean: float | None


class ConfusionMatrix(BaseModel):
    labels: list[str]
    matrix: list[list[int]] = Field(description="Linhas = nível alvo, colunas = nível previsto.")


class ReflectionStats(BaseModel):
    doc_id: str
    cells: int
    pct_approved_first: float
    pct_approved_final: float
    mean_attempts: float
    refined_cells: int
    stagnated: int
    regressions: int
    extra_llm_calls: int
    extra_tokens: int
    extra_cost_usd: float
    extra_latency_s: float


class SummaryResponse(BaseModel):
    documents: list[str]
    levels: list[LevelSummary]
    confusion: dict[str, ConfusionMatrix] = Field(description="Por sistema: 'pipeline' e, se avaliado, 'baseline'.")
    pass_rate_by_system: dict[str, float]
    reflection: list[ReflectionStats]
    notes: list[str]
    cells: list["CellMetrics"] = Field(default_factory=list, description="Métricas da versão entregue de cada saída.")
    node_costs: list["NodeCost"] = Field(default_factory=list, description="Pipeline, somado entre documentos.")


# --- referência e telemetria: glossário, termos por célula, limiares, custo por nó ---


class GlossaryTermOut(BaseModel):
    termo: str
    variacoes: list[str]
    nivel_minimo: Audience
    analogia_iniciante: str
    status: Literal["revisado", "pendente_revisao"]


class TermOccurrenceOut(BaseModel):
    termo: str
    surface: str = Field(description="Trecho exato do texto que casou (para destacar).")
    sentence_index: int
    sentence: str
    needs_context: bool = Field(description="O nível mínimo do termo é superior ao nível do texto.")
    marker: str | None = Field(description="Marcador de explicação encontrado (mesma frase, anterior ou seguinte por anáfora).")
    contextualized: bool


class CellTermsResponse(BaseModel):
    run_id: str
    audience: Audience
    format: Format
    attempt: int
    occurrences: list[TermOccurrenceOut]


class BoundOut(BaseModel):
    min: float | None = None
    max: float | None = None


class ThresholdsResponse(BaseModel):
    levels: dict[str, dict[str, BoundOut]] = Field(description="Por nível: flesch_pt, term_density, term_context_pct.")
    common: dict[str, BoundOut] = Field(description="Comuns a todos os níveis (fidelidade e judge).")


class CellMetrics(BaseModel):
    system: str
    doc_id: str
    audience: Audience
    format: Format
    passed: bool
    predicted_level: Audience | None
    metrics: dict[str, float]


class NodeCost(BaseModel):
    node: str = Field(description="extractor, adapter, formatter, refiner, evaluator:deterministic, evaluator:claims, evaluator:judge")
    calls: int
    llm_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float = Field(description="Soma das latências das chamadas (chamadas paralelas se sobrepõem).")


RunResults.model_rebuild()
SummaryResponse.model_rebuild()


# --- etapas complementares do experimento ---

class VarianceRow(BaseModel):
    metric: str
    tipo: Literal["deterministica", "llm"]
    media: float
    desvio_medio: float = Field(description="Desvio padrão médio entre repetições, por saída.")
    desvio_max: float


class TradeoffRow(BaseModel):
    config: str
    modelo_geracao: str
    max_tentativas: int
    aprovacao: float
    flesch_medio: float
    densidade_media: float
    fidelidade_media: float | None = None
    tentativas_medias: float
    chamadas_llm: int
    tokens: int
    custo_usd: float
    latencia_s: float
    latencia_estimada: bool = Field(description="True quando a latência vem do caminho crítico da 1ª passada.")


class AgreementRow(BaseModel):
    dimensao: str
    n: int
    concordancia: float | None = None
    ic95_inf: float | None = None
    ic95_sup: float | None = None
    kappa: float | None = None


class ExperimentResponse(BaseModel):
    date: str | None = None
    repeats: int | None = Field(default=None, description="Avaliações por saída na variância.")
    variance: list[VarianceRow] = Field(default_factory=list)
    tradeoffs: list[TradeoffRow] = Field(default_factory=list)
    agreement: list[AgreementRow] = Field(default_factory=list)
