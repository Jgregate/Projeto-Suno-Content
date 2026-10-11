"""Chama a API real. Fora da execução padrão; rode com:  uv run pytest -m integration"""

import pytest

from backend.llm import get_llm
from backend.schemas import AdaptedContent, Audience

pytestmark = pytest.mark.integration


def test_fast_model_returns_structured_output():
    llm = get_llm("fast")
    result = llm.structured(
        AdaptedContent,
        "Responda no schema pedido. Use a âncora A01 em todos os claims.",
        "Nível: iniciante. Âncora [A01]: O Copom manteve a Selic em 15,00% a.a.",
    )
    assert isinstance(result.parsed, AdaptedContent)
    assert result.parsed.claims and all(c.anchor_ids for c in result.parsed.claims)
    assert result.input_tokens > 0 and result.output_tokens > 0
    assert result.parsed.audience in Audience


def _anchor():
    from backend.schemas import FactualAnchor

    return FactualAnchor(id="A01", claim="O Copom reduziu a Selic em 0,50 p.p., para 13,75% a.a.",
                         numbers=["0,50 p.p.", "13,75%"], source_excerpt="reduzir a taxa Selic em 0,50 ponto percentual, para 13,75% a.a.", page=1)


def test_claim_check_flags_contradiction():
    from backend.evaluator.llm_checks import check_claims

    check, run = check_claims(get_llm("judge", temperature=0), "O Copom aumentou a Selic para 13,75%.", [_anchor()], "t")
    assert any(c.verdict == "contradita" and c.anchor_id == "A01" for c in check.claims)
    assert run.model and run.input_tokens > 0


def test_judge_returns_all_criteria_with_literal_evidence():
    from backend.evaluator.llm_checks import CRITERIA, judge
    from backend.schemas import Format

    text = "O Banco Central baixou os juros. A Selic, que é o preço do dinheiro, caiu para 13,75% ao ano."
    verdict, _ = judge(get_llm("judge", temperature=0), text, Audience.BEGINNER, Format.ARTICLE, ["Selic reduzida"], "t")
    assert sorted(s.criterion for s in verdict.scores) == sorted(CRITERIA)
    assert all(1 <= s.score <= 5 and s.evidence for s in verdict.scores)
