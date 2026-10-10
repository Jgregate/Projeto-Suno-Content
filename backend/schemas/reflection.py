"""Schemas do reflection loop: histórico de tentativas e status final por célula."""

from typing import Literal

from pydantic import BaseModel, Field

from backend.schemas.content import GeneratedContent
from backend.schemas.evaluation import EvaluationReport


class AttemptRecord(BaseModel):
    """Uma tentativa de uma célula: texto, relatório, nota agregada e custo."""

    attempt: int = Field(ge=1)
    content: GeneratedContent
    report: EvaluationReport
    aggregate_score: float = Field(description="Nota agregada 0..1 usada para parada e escolha da melhor tentativa.")
    injected_feedback: str = Field(default="", description="Feedback que gerou esta tentativa (vazio na 1ª).")
    regressions: list[str] = Field(default_factory=list, description="Métricas que passavam e passaram a reprovar.")
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = Field(default=0.0, description="Geração/refino + avaliação desta tentativa.")





class CellStatus(BaseModel):
    """Situação final de uma célula depois do loop."""

    status: str = Field(description="'aprovado', 'aprovado_apos_N' (N refinamentos) ou 'reprovado_final'.")
    attempts: int
    delivered_attempt: int = Field(description="Tentativa entregue (a aprovada ou a de melhor nota).")
    best_score: float
    stop_reason: Literal["aprovado", "max_tentativas", "estagnou", "erro_refino"]
    regressions: list[str] = Field(default_factory=list)
