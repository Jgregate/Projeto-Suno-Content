"""LLM falso: devolve objetos válidos por schema, sem rede e sem custo."""

import threading

from backend.evaluator.llm_checks import CRITERIA, AtomicClaim, ClaimCheck, CriterionScore, JudgeVerdict
from backend.llm import LLMResult
from backend.schemas import (
    AdaptedClaim,
    AdaptedContent,
    ArticleBody,
    Audience,
    CarouselBody,
    ExtractionResult,
    FactualAnchor,
    KeyNumber,
    ScriptBlock,
    Section,
    Slide,
    VideoScriptBody,
)

# Números presentes no texto do documento de teste (ver make_doc em test_graph.py).
VALID_NUMBER = "15,00%"
INVALID_NUMBER = "99,9%"


def _extraction() -> ExtractionResult:
    return ExtractionResult(
        key_points=["Copom manteve a Selic", "Expectativas seguem desancoradas"],
        anchors=[
            FactualAnchor(id="A01", claim="Selic mantida", numbers=[VALID_NUMBER], source_excerpt="manteve a Selic em 15,00%", page=1),
            FactualAnchor(id="A02", claim="Inflação em queda", numbers=[], source_excerpt="inflação segue em queda", page=1),
            FactualAnchor(id="A03", claim="Número inventado", numbers=[INVALID_NUMBER], source_excerpt="...", page=1),
        ],
        key_numbers=[KeyNumber(label="Selic", value=VALID_NUMBER, anchor_id="A01")],
    )


def _script(long_speech: bool) -> VideoScriptBody:
    speech = " ".join(["palavra"] * 60) if long_speech else "Os juros ficaram parados."
    return VideoScriptBody(blocks=[
        ScriptBlock(start_s=0, end_s=3, visual_hook="15% na tela", speech=speech, anchor_ids=["A01"]),
        ScriptBlock(start_s=3, end_s=30, visual_hook="gráfico", speech=speech, anchor_ids=["A02"]),
        ScriptBlock(start_s=30, end_s=55, visual_hook="resumo", speech=speech, anchor_ids=["A01"]),
    ])


class FakeLLM:
    def __init__(
        self, model_id: str = "fake:model", long_script: bool = False, judge_score: int = 5, contradict: bool = False
    ) -> None:
        self.model_id = model_id
        self.long_script = long_script
        self.judge_score = judge_score
        self.contradict = contradict
        self.calls: list[str] = []
        self.systems: list[str] = []
        self._lock = threading.Lock()

    def structured(self, schema, system: str, user: str) -> LLMResult:
        with self._lock:
            self.calls.append(schema.__name__)
            self.systems.append(system)
        builders = {
            ExtractionResult: _extraction,
            AdaptedContent: lambda: AdaptedContent(
                audience=Audience.BEGINNER,
                angle="impacto no bolso",
                claims=[AdaptedClaim(text="Os juros ficaram parados.", anchor_ids=["A01"])],
                takeaway="nada muda por ora",
            ),
            ArticleBody: lambda: ArticleBody(
                title="Juros parados", subtitle="O BC manteve a taxa.",
                sections=[Section(heading="O que houve", body="Os juros ficaram parados.", anchor_ids=["A01"])],
            ),
            CarouselBody: lambda: CarouselBody(slides=[
                Slide(role="gancho", title="E os juros?", text="Ficaram parados.", anchor_ids=["A01"]),
                *[Slide(role="corpo", title=f"Ponto {i}", text="...", anchor_ids=["A02"]) for i in range(3)],
                Slide(role="conclusao", title="Resumo", text="Salve o post.", anchor_ids=["A01"]),
            ]),
            VideoScriptBody: lambda: _script(self.long_script),
            ClaimCheck: lambda: ClaimCheck(claims=[
                AtomicClaim(claim="Os juros ficaram parados.", verdict="contradita" if self.contradict else "sustentada", anchor_id="A01"),
            ]),
            JudgeVerdict: lambda: JudgeVerdict(scores=[
                CriterionScore(criterion=c, score=self.judge_score, evidence="juros", rationale="ok") for c in CRITERIA
            ]),
        }
        return LLMResult(builders[schema](), input_tokens=len(system + user) // 4, output_tokens=100)
