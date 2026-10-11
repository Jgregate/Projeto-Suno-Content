import pytest

from backend.graph.build import build_graph
from backend.prompts import prompts_hash
from backend.schemas import (
    ArticleBody,
    Audience,
    CarouselBody,
    Format,
    GeneratedContent,
    GraphState,
    Page,
    SourceDocument,
    VideoScriptBody,
    cell_key,
)
from tests.fakes import FakeLLM

TEXT = "O Copom manteve a Selic em 15,00% a.a. A inflação segue em queda. Os juros reais seguem altos."


def make_doc() -> SourceDocument:
    return SourceDocument(id="ata-teste", title="Ata", text=TEXT, pages=[Page(number=1, text=TEXT)])


@pytest.fixture(scope="module")
def result() -> tuple[GraphState, FakeLLM, FakeLLM]:
    fast, strong = FakeLLM("fake:fast"), FakeLLM("fake:strong")
    # max_attempts=1: só a 1ª passada (o loop tem testes próprios em test_reflection.py)
    final = build_graph(fast, strong, max_attempts=1).invoke(GraphState(document=make_doc(), prompts_hash=prompts_hash()))
    return GraphState.model_validate(final), fast, strong


def test_nine_outputs_with_right_schemas(result):
    state, _, _ = result
    expected = {Format.ARTICLE: ArticleBody, Format.CAROUSEL: CarouselBody, Format.VIDEO_SCRIPT: VideoScriptBody}
    assert len(state.outputs) == 9
    for audience in Audience:
        for fmt, body in expected.items():
            out = state.outputs[cell_key(audience, fmt)]
            assert isinstance(out, GeneratedContent)
            assert isinstance(out.content, body)
            assert out.audience == audience and out.attempt == 1
            assert out.anchor_ids


def test_roles_get_the_right_model(result):
    _, fast, strong = result
    # strong: extractor + avaliação (sem judge separado, claims e judge usam o strong)
    assert strong.calls.count("ExtractionResult") == 1
    assert strong.calls.count("ClaimCheck") == 9 and strong.calls.count("JudgeVerdict") == 9
    assert fast.calls.count("AdaptedContent") == 3
    assert len(fast.calls) == 3 + 9


def test_adapted_per_level_and_glossary_terms(result):
    state, _, _ = result
    assert set(state.adapted) == {a.value for a in Audience}
    assert all(state.adapted[a.value].audience == a for a in Audience)
    assert {"Copom", "Selic", "juros reais"} <= set(state.doc_terms)


def test_invalid_anchor_flagged_not_dropped(result):
    state, _, _ = result
    anchors = {a.id: a for a in state.extraction.anchors}
    assert anchors["A01"].valid
    assert not anchors["A03"].valid and anchors["A03"].invalid_numbers == ["99,9%"]
    assert "A03" not in {a.id for a in state.extraction.valid_anchors}
    assert any("A03" in w for w in state.warnings)


def test_telemetry_and_attempts(result):
    state, _, _ = result
    llm_runs = [r for r in state.node_log if r.model]
    assert len(llm_runs) == 13 + 18
    assert sum(r.node.startswith("evaluator:") and r.model is not None for r in state.node_log) == 18
    assert all(r.input_tokens > 0 and r.latency_ms >= 0 for r in llm_runs)
    assert state.attempts == dict.fromkeys(state.outputs, 1)
    assert len(state.prompts_hash) == 12


def test_long_script_is_flagged_not_rejected():
    fast = FakeLLM("fake:fast", long_script=True)
    final = GraphState.model_validate(build_graph(fast, FakeLLM(), max_attempts=1).invoke(GraphState(document=make_doc())))
    script = final.outputs[cell_key(Audience.BEGINNER, Format.VIDEO_SCRIPT)]
    assert any("palavras" in w for w in script.warnings)
    assert any("roteiro" in w and "palavras" in w for w in final.warnings)


def test_every_cell_gets_a_report_and_route_decides(result):
    state, _, _ = result
    assert set(state.reports) == set(state.outputs)
    for reports in state.reports.values():
        names = {m.name for m in reports[-1].metrics}
        assert {"flesch_pt", "term_density", "numeric_grounding", "claim_support", "judge_tom"} <= names
    # textos falsos são curtos -> baixa confiabilidade; com max_attempts=1 tudo fecha na 1ª tentativa
    assert any(r[-1].flags == ["baixa_confiabilidade"] for r in state.reports.values())
    assert set(state.final_status) == set(state.outputs) and not state.to_refine


def test_separate_judge_model_is_used_for_evaluation():
    fast, strong, judge = FakeLLM("fake:fast"), FakeLLM("fake:strong"), FakeLLM("fake:judge", contradict=True)
    final = GraphState.model_validate(build_graph(fast, strong, judge=judge, max_attempts=1).invoke(GraphState(document=make_doc())))
    assert strong.calls == ["ExtractionResult"]
    assert judge.calls.count("JudgeVerdict") == 9
    report = final.reports[cell_key(Audience.ADVANCED, Format.ARTICLE)][-1]
    assert report.metric("claim_contradictions").score == 1 and not report.passed
    assert "contradiz a âncora A01" in report.feedback


def test_claims_checker_can_use_its_own_model():
    judge, claims = FakeLLM("fake:judge"), FakeLLM("fake:claims")
    build_graph(FakeLLM("fake:fast"), FakeLLM("fake:strong"), judge=judge, claims=claims, max_attempts=1).invoke(
        GraphState(document=make_doc())
    )
    assert set(judge.calls) == {"JudgeVerdict"} and judge.calls.count("JudgeVerdict") == 9
    assert set(claims.calls) == {"ClaimCheck"} and claims.calls.count("ClaimCheck") == 9


def test_deterministic_only_mode_makes_no_eval_calls():
    strong = FakeLLM("fake:strong")
    final = GraphState.model_validate(build_graph(FakeLLM(), strong, use_llm_eval=False, max_attempts=1).invoke(GraphState(document=make_doc())))
    assert strong.calls == ["ExtractionResult"]
    assert all("judge_tom" not in {m.name for m in r[-1].metrics} for r in final.reports.values())


class BrokenLLM(FakeLLM):
    """Modelo que nunca entrega um schema de formato válido."""

    def structured(self, schema, system, user):
        if schema.__name__ in {"ArticleBody", "CarouselBody", "VideoScriptBody"}:
            raise ValueError("saída inválida")
        return super().structured(schema, system, user)


def test_formatter_falls_back_to_strong_model_when_schema_fails():
    fast, strong = BrokenLLM("fake:fast"), FakeLLM("fake:strong")
    final = GraphState.model_validate(
        build_graph(fast, strong, max_attempts=1, use_llm_eval=False).invoke(GraphState(document=make_doc(), prompts_hash=prompts_hash()))
    )
    assert len(final.outputs) == 9  # nenhuma célula perdida
    fmt_runs = [r for r in final.node_log if r.node == "formatter"]
    assert {r.model for r in fmt_runs} == {"fake:strong"}
    assert sum("repetindo com fake:strong" in w for w in final.warnings) == 9
