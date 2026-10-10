"""Estado compartilhado do grafo LangGraph.

Os campos com reducer (`Annotated[..., reducer]`) podem ser escritos por
nós paralelos (adaptadores/formatadores) sem que um sobrescreva o outro.
"""

import operator
from typing import Annotated

from pydantic import BaseModel, Field

from backend.schemas.content import AdaptedContent, Audience, GeneratedContent
from backend.schemas.document import ExtractionResult, SourceDocument
from backend.schemas.evaluation import EvaluationReport
from backend.schemas.reflection import AttemptRecord, CellStatus


def merge_dicts(left: dict, right: dict) -> dict:
    """Reducer: junta dicionários; em conflito, vence o valor mais novo."""
    return {**left, **right}


class NodeRun(BaseModel):
    """Telemetria de uma execução de nó (custo em tokens, custo estimado e latência)."""

    node: str
    cell: str | None = Field(default=None, description="Célula 'nivel:formato' ou nível, se aplicável.")
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    attempt: int | None = Field(default=None, description="Tentativa da célula (refiner/avaliador).")


class GraphState(BaseModel):
    """Estado do pipeline do documento até os relatórios de avaliação."""

    document: SourceDocument
    prompts_hash: str = Field(default="", description="Hash da versão dos prompts usada na execução.")
    extraction: ExtractionResult | None = None
    doc_terms: list[str] = Field(
        default_factory=list, description="Termos do glossário encontrados no documento-fonte."
    )
    adapted: Annotated[dict[str, AdaptedContent], merge_dicts] = Field(
        default_factory=dict, description="Conteúdo adaptado por nível (chave = nível)."
    )
    outputs: Annotated[dict[str, GeneratedContent], merge_dicts] = Field(
        default_factory=dict, description="Última versão por célula, chave 'nivel:formato'."
    )
    reports: Annotated[dict[str, list[EvaluationReport]], merge_dicts] = Field(
        default_factory=dict, description="Histórico de relatórios por célula (um por tentativa)."
    )
    attempts: Annotated[dict[str, int], merge_dicts] = Field(
        default_factory=dict, description="Contador de tentativas por célula."
    )
    warnings: Annotated[list[str], operator.add] = Field(
        default_factory=list, description="Avisos de validação determinística (âncoras, roteiro...)."
    )
    node_log: Annotated[list[NodeRun], operator.add] = Field(default_factory=list)

    # --- reflection loop ---
    force_drift: Audience | None = Field(
        default=None, description="Demo: esse nível é gerado com as regras do Avançado na 1ª tentativa."
    )
    history: Annotated[dict[str, list[AttemptRecord]], merge_dicts] = Field(
        default_factory=dict, description="Todas as tentativas por célula."
    )
    final_status: Annotated[dict[str, CellStatus], merge_dicts] = Field(default_factory=dict)
    to_refine: list[str] = Field(default_factory=list, description="Células que o refiner reescreve na próxima volta.")
