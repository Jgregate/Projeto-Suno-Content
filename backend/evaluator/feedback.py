"""Feedback acionável para o reflection loop.

Gerado de forma determinística a partir das métricas reprovadas. Cada linha traz o valor,
o limiar, a causa medida e a correção sugerida, com o trecho do texto quando aplicável.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.evaluator.hybrid import Evaluation

TARGET_WPS = 15  # alvo de palavras por frase sugerido quando o Flesch está baixo
MAX_ITEMS = 5


def _num(x: float) -> str:
    """Formata com uma casa decimal para não arredondar o valor até o limiar."""
    return f"{x:.1f}".rstrip("0").rstrip(".")


def _short(text: str, n: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def build_feedback(ev: Evaluation, missing_jargon: list[str] | None = None) -> str:
    report, read, terms = ev.report, ev.readability, ev.terms
    lines: list[str] = []

    for m in report.failed_metrics:
        if m.name == "flesch_pt":
            if m.direction in ("min", "range") and m.score < m.threshold:
                causes = []
                if read.words_per_sentence > TARGET_WPS + 2:  # tolerância para frases já próximas do alvo
                    causes.append(f"frases com média de {read.words_per_sentence:.0f} palavras, encurte para ~{TARGET_WPS}")
                causes.append(f"{read.pct_polysyllables:.0f}% das palavras têm 4+ sílabas, troque por palavras curtas")
                lines.append(
                    f"Flesch {_num(m.score)} < {m.threshold:g} exigido; " + "; ".join(causes)
                    + f". Frase mais longa: \"{_short(read.longest_sentences[0])}\""
                )
            else:
                lines.append(
                    f"Flesch {_num(m.score)} > {m.threshold_max:g}: simples demais para o nível; use o vocabulário de mercado "
                    f"esperado e frases um pouco mais completas, sem infantilizar."
                )
        elif m.name == "term_density":
            if m.direction in ("min", "range") and m.score < m.threshold:
                hint = f" Termos da fonte que podem voltar: {', '.join(missing_jargon[:MAX_ITEMS])}." if missing_jargon else ""
                lines.append(
                    f"Densidade de termos técnicos {m.score:.1f}/100 palavras < {m.threshold:g}: texto trivializado, "
                    f"preserve o jargão do documento.{hint}"
                )
            else:
                used = sorted({o.termo for o in terms.occurrences})
                lines.append(
                    f"Densidade de termos técnicos {m.score:.1f}/100 palavras > {(m.threshold_max or m.threshold):g}: "
                    f"corte ou troque por palavras do dia a dia: {', '.join(used[:MAX_ITEMS])}."
                )
        elif m.name == "term_context_pct":
            items = [
                f"'{o.termo}' sem explicação na frase {o.sentence_index + 1} (\"{_short(o.sentence, 70)}\")"
                for o in terms.uncontextualized[:MAX_ITEMS]
            ]
            lines.append(
                f"{m.score:.0f}% dos termos contextualizados < {m.threshold:g}% exigido: " + "; ".join(items)
                + ". Explique cada um na mesma frase ou na anterior (ex.: 'ou seja', 'funciona como', parênteses), ou logo na frase seguinte começando por 'Esse/Essa/Isso'."
            )
        elif m.name == "numeric_grounding":
            lines.append(
                f"Alucinação numérica: {', '.join(ev.ungrounded)} não aparece(m) na fonte nem nas âncoras. "
                f"Remova ou use o valor exato da âncora."
            )
        elif m.name == "claim_support" and ev.claims:
            unsupported = [c.claim for c in ev.claims.by_verdict("nao_sustentada")][:MAX_ITEMS]
            lines.append(
                f"Fidelidade {m.score:.2f} < {m.threshold:g}: afirmações sem âncora: "
                + "; ".join(f"\"{_short(c, 80)}\"" for c in unsupported)
                + ". Remova ou reescreva preservando a condicionante da fonte."
            )
        elif m.name == "claim_contradictions" and ev.claims:
            for c in ev.claims.by_verdict("contradita")[:MAX_ITEMS]:
                lines.append(f"Afirmação \"{_short(c.claim, 80)}\" contradiz a âncora {c.anchor_id}: {c.justification}")
        elif m.name.startswith("judge_") and ev.verdict:
            score = ev.verdict.get(m.name.removeprefix("judge_"))
            lines.append(f"Judge/{score.criterion} {score.score} < {m.threshold:g}: \"{_short(score.evidence, 80)}\" — {score.rationale}")

    if "baixa_confiabilidade" in report.flags:
        lines.append(f"(Aviso: texto com {read.words} palavras; legibilidade e densidade têm baixa confiabilidade.)")
    return "\n".join(f"- {line}" for line in lines)
