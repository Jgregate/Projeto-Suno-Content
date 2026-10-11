"""Avaliador híbrido: combina as métricas de uma célula num `EvaluationReport`.

Métricas determinísticas: legibilidade, densidade e contextualização de termos, grounding numérico.
Métricas com LLM (opcionais): fidelidade por afirmações atômicas e LLM Judge.
Sem `claims_llm` e `judge_llm`, só a parte determinística roda, com resultado reprodutível.
"""

import time
from dataclasses import dataclass, field

from backend.evaluator.feedback import build_feedback
from backend.evaluator.glossary import TermMatcher
from backend.evaluator.level_classifier import predict_level
from backend.evaluator.llm_checks import CRITERIA, ClaimCheck, JudgeVerdict, check_claims, judge
from backend.evaluator.numbers import ungrounded_quantities
from backend.evaluator.readability import LOW_RELIABILITY, Readability, readability
from backend.evaluator.term_density import TermDensity, term_density
from backend.evaluator.thresholds import Thresholds, load_thresholds
from backend.llm import LLMClient
from backend.schemas import (
    Audience,
    ClaimVerdict,
    EvaluationReport,
    ExtractionResult,
    FactualAnchor,
    Format,
    GeneratedContent,
    JudgeScore,
    NodeRun,
    SourceDocument,
)


@dataclass
class Evaluation:
    """Resultado da avaliação de uma célula: relatório e os insumos usados no feedback."""

    report: EvaluationReport
    readability: Readability
    terms: TermDensity
    ungrounded: list[str]
    claims: ClaimCheck | None
    verdict: JudgeVerdict | None
    predicted_level: Audience
    runs: list[NodeRun] = field(default_factory=list)


def evaluation_text(output: GeneratedContent) -> str:
    """Artigo = texto inteiro; carrossel = slides concatenados; roteiro = só a fala."""
    return output.plain_text()


class HybridEvaluator:
    def __init__(
        self,
        matcher: TermMatcher,
        claims_llm: LLMClient | None = None,
        judge_llm: LLMClient | None = None,
        thresholds: Thresholds | None = None,
    ) -> None:
        self.matcher = matcher
        self.claims_llm = claims_llm
        self.judge_llm = judge_llm
        self.thresholds = thresholds or load_thresholds()
        self._source_terms: dict[str, list[str]] = {}

    def evaluate_text(
        self,
        text: str,
        audience: Audience,
        fmt: Format,
        source: SourceDocument,
        extraction: ExtractionResult | None = None,
        anchor_ids: list[str] | None = None,
        attempt: int = 1,
    ) -> Evaluation:
        cell = f"{audience.value}:{fmt.value}"
        bounds = self.thresholds.for_cell(audience, fmt)
        runs: list[NodeRun] = []

        # --- determinístico ---
        start = time.perf_counter()
        read = readability(text)
        terms = term_density(text, audience, self.matcher)
        valid = extraction.valid_anchors if extraction else []
        fact_cfg = self.thresholds.factuality
        ungrounded = ungrounded_quantities(
            text,
            [source.text, *(" ".join(a.numbers) for a in valid)],
            rel_tolerance=fact_cfg["rel_tolerance"],
            allow_rounding=fact_cfg["allow_rounding"],
        )
        metrics = [
            bounds["flesch_pt"].metric("flesch_pt", read.flesch_pt, f"{read.words_per_sentence} palavras/frase; {read.pct_polysyllables}% com 4+ sílabas"),
            bounds["term_density"].metric("term_density", terms.density, ", ".join(o.termo for o in terms.occurrences)),
            bounds["term_context_pct"].metric("term_context_pct", terms.context_pct, "; ".join(o.termo for o in terms.uncontextualized)),
            bounds["numeric_grounding"].metric("numeric_grounding", len(ungrounded), ", ".join(ungrounded)),
        ]
        runs.append(NodeRun(node="evaluator:deterministic", cell=cell, latency_ms=round((time.perf_counter() - start) * 1000, 1)))

        # --- LLM: fidelidade por afirmações ---
        claims = None
        if self.claims_llm is not None:
            wanted = set(anchor_ids or [])
            anchors: list[FactualAnchor] = [a for a in valid if a.id in wanted] or valid
            claims, run = check_claims(self.claims_llm, text, anchors, cell)
            runs.append(run)
            contradicted = claims.by_verdict("contradita")
            metrics += [
                bounds["claim_support"].metric("claim_support", round(claims.support_ratio, 3), f"{len(claims.claims)} afirmações"),
                bounds["claim_contradictions"].metric("claim_contradictions", len(contradicted), "; ".join(c.claim for c in contradicted)),
            ]

        # --- LLM Judge ---
        verdict = None
        if self.judge_llm is not None:
            verdict, run = judge(self.judge_llm, text, audience, fmt, extraction.key_points if extraction else [], cell)
            runs.append(run)
            for criterion in CRITERIA:
                score = verdict.get(criterion)
                literal = score.evidence.strip().strip('"') in text
                note = "" if literal else " [evidência não encontrada no texto]"
                metrics.append(bounds["judge"].metric(f"judge_{criterion}", score.score, f"\"{score.evidence}\"{note}"))

        flags = [LOW_RELIABILITY] if read.low_reliability else []
        report = EvaluationReport(
            audience=audience, format=fmt, attempt=attempt, metrics=metrics, flags=flags,
            # exibidos na interface (afirmação → âncora, justificativa do judge)
            claims=[ClaimVerdict(**c.model_dump()) for c in claims.claims] if claims else [],
            judge=[JudgeScore(**s.model_dump()) for s in verdict.scores] if verdict else [],
        )
        evaluation = Evaluation(
            report=report,
            readability=read,
            terms=terms,
            ungrounded=ungrounded,
            claims=claims,
            verdict=verdict,
            predicted_level=predict_level({"flesch_pt": read.flesch_pt, "term_density": terms.density}, self.thresholds),
            runs=runs,
        )
        missing = self._missing_jargon(source, terms) if audience == Audience.ADVANCED else []
        report.feedback = build_feedback(evaluation, missing_jargon=missing)
        return evaluation

    def evaluate(self, output: GeneratedContent, source: SourceDocument, extraction: ExtractionResult | None) -> Evaluation:
        return self.evaluate_text(
            evaluation_text(output), output.audience, output.format, source, extraction, output.anchor_ids, output.attempt
        )

    def _missing_jargon(self, source: SourceDocument, terms: TermDensity) -> list[str]:
        """Termos do glossário presentes na fonte e ausentes no texto; sugeridos ao Avançado trivializado."""
        if source.id not in self._source_terms:
            self._source_terms[source.id] = [t.termo for t in self.matcher.terms_in(source.text)]
        used = {o.termo for o in terms.occurrences}
        return [t for t in self._source_terms[source.id] if t not in used]
