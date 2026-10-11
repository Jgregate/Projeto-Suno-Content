"""Métricas do avaliador que usam LLM: checker de afirmações e LLM Judge (temperatura 0).

Mitigação de vieses do judge:
1. Uma chamada por texto, sem comparação entre textos (evita viés de posição).
2. O tamanho do texto não é critério nem é informado ao modelo.
3. Cada nota exige um trecho literal do texto como evidência; trecho ausente do texto é
   sinalizado no relatório.
4. Rubrica por nível, escala 1-5 e critérios separados, sem nota global.
5. Modelo configurável (LLM_JUDGE_MODEL), preferencialmente diferente do gerador.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.config import EVAL_PROMPTS_DIR
from backend.llm import LLMClient
from backend.nodes.common import call_llm
from backend.prompts import load_text, render
from backend.schemas import Audience, FactualAnchor, Format, NodeRun

Verdict = Literal["sustentada", "nao_sustentada", "contradita"]
Criterion = Literal["adequacao_publico", "tom", "nuances", "formato"]
CRITERIA: tuple[str, ...] = ("adequacao_publico", "tom", "nuances", "formato")


class AtomicClaim(BaseModel):
    claim: str
    verdict: Verdict
    anchor_id: str | None = None
    justification: str = ""


class ClaimCheck(BaseModel):
    """Afirmações atômicas do texto classificadas contra as âncoras."""

    claims: list[AtomicClaim] = Field(default_factory=list)

    @property
    def support_ratio(self) -> float:
        return sum(c.verdict == "sustentada" for c in self.claims) / len(self.claims) if self.claims else 1.0

    def by_verdict(self, verdict: Verdict) -> list[AtomicClaim]:
        return [c for c in self.claims if c.verdict == verdict]


class CriterionScore(BaseModel):
    criterion: Criterion
    score: int = Field(ge=1, le=5)
    evidence: str = Field(description="Trecho literal do texto avaliado que justifica a nota.")
    rationale: str


class JudgeVerdict(BaseModel):
    scores: list[CriterionScore]

    @field_validator("scores")
    @classmethod
    def _one_per_criterion(cls, scores: list[CriterionScore]) -> list[CriterionScore]:
        if sorted(s.criterion for s in scores) != sorted(CRITERIA):
            raise ValueError(f"Esperado exatamente um score por critério: {CRITERIA}")
        return scores

    def get(self, criterion: str) -> CriterionScore:
        return next(s for s in self.scores if s.criterion == criterion)


def check_claims(
    llm: LLMClient, text: str, anchors: list[FactualAnchor], cell: str
) -> tuple[ClaimCheck, NodeRun]:
    anchors_txt = "\n".join(f"[{a.id}] {a.claim} | fonte: \"{a.source_excerpt}\"" for a in anchors) or "(nenhuma)"
    system, user = render("claims", EVAL_PROMPTS_DIR, anchors=anchors_txt, text=text)
    return call_llm("evaluator:claims", cell, llm, ClaimCheck, system, user)


def judge(
    llm: LLMClient, text: str, audience: Audience, fmt: Format, key_points: list[str], cell: str
) -> tuple[JudgeVerdict, NodeRun]:
    system, user = render(
        "judge",
        EVAL_PROMPTS_DIR,
        rubric=load_text(f"rubric_{audience.value}", EVAL_PROMPTS_DIR),
        format_rules=load_text(f"fmt_{fmt.value}", EVAL_PROMPTS_DIR),
        audience=audience.value,
        format=fmt.value,
        key_points="\n".join(f"- {p}" for p in key_points) or "(não disponível)",
        text=text,
    )
    return call_llm("evaluator:judge", cell, llm, JudgeVerdict, system, user)
