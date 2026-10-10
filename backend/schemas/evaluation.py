"""Schemas do Hybrid Evaluator: resultado por métrica e relatório por célula."""

from typing import Literal

from pydantic import BaseModel, Field, computed_field

from backend.schemas.content import Audience, Format


class MetricResult(BaseModel):
    """Nota de uma métrica contra o limiar do nível/formato.

    `direction`:
    - "min":   passa se score >= threshold
    - "max":   passa se score <= threshold
    - "range": passa se threshold <= score <= threshold_max
    - "info":  só reporta (ex.: Flesch no Avançado, que não tem mínimo)
    """

    name: str = Field(description="Ex.: 'flesch_pt', 'term_density', 'numeric_grounding', 'judge_tom'.")
    score: float
    threshold: float = 0.0
    threshold_max: float | None = None
    direction: Literal["min", "max", "range", "info"] = "min"
    details: str = Field(default="", description="Evidência curta (termos, frases, números, trechos).")

    @computed_field
    @property
    def passed(self) -> bool:
        if self.direction == "min":
            return self.score >= self.threshold
        if self.direction == "max":
            return self.score <= self.threshold
        if self.direction == "range":
            upper = self.threshold_max if self.threshold_max is not None else float("inf")
            return self.threshold <= self.score <= upper
        return True

    def bound_text(self) -> str:
        """Limiar legível para o feedback (ex.: '>= 60', 'entre 2 e 6')."""
        return {
            "min": f">= {self.threshold:g}",
            "max": f"<= {self.threshold:g}",
            "range": f"entre {self.threshold:g} e {self.threshold_max:g}" if self.threshold_max is not None else f">= {self.threshold:g}",
            "info": "sem limiar",
        }[self.direction]


class ClaimVerdict(BaseModel):
    """Afirmação atômica do texto classificada contra as âncoras (saída do checker com LLM)."""

    claim: str
    verdict: Literal["sustentada", "nao_sustentada", "contradita"]
    anchor_id: str | None = None
    justification: str = ""


class JudgeScore(BaseModel):
    """Nota do LLM Judge num critério, com o trecho literal que a justifica."""

    criterion: Literal["adequacao_publico", "tom", "nuances", "formato"]
    score: int
    evidence: str
    rationale: str


class EvaluationReport(BaseModel):
    """Relatório de uma célula numa tentativa; alimenta o reflection loop."""

    audience: Audience
    format: Format
    attempt: int = Field(ge=1)
    metrics: list[MetricResult] = Field(min_length=1)
    flags: list[str] = Field(default_factory=list, description="Ex.: 'baixa_confiabilidade' (texto < 100 palavras).")
    feedback: str = Field(default="", description="Instruções de correção injetadas no retry.")
    claims: list[ClaimVerdict] = Field(default_factory=list, description="Veredito por afirmação (vazio sem LLM).")
    judge: list[JudgeScore] = Field(default_factory=list, description="Notas do judge com evidência (vazio sem LLM).")

    @computed_field
    @property
    def passed(self) -> bool:
        return all(m.passed for m in self.metrics)

    @property
    def failed_metrics(self) -> list[MetricResult]:
        return [m for m in self.metrics if not m.passed]

    def metric(self, name: str) -> MetricResult | None:
        return next((m for m in self.metrics if m.name == name), None)
