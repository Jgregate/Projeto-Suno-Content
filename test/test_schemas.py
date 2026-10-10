import pytest
from pydantic import ValidationError

from backend.schemas import (
    ArticleBody,
    Audience,
    CarouselBody,
    DocumentType,
    EvaluationReport,
    ExtractionResult,
    FactualAnchor,
    Format,
    GeneratedContent,
    GraphState,
    MetricResult,
    Page,
    ScriptBlock,
    Section,
    Slide,
    SourceDocument,
    VideoScriptBody,
    cell_key,
)


def make_doc() -> SourceDocument:
    return SourceDocument(
        id="ata-copom",
        doc_type=DocumentType.COPOM_MINUTES,
        title="Ata do Copom",
        text="O Comitê manteve a Selic em 15,00%.",
        pages=[Page(number=1, text="O Comitê manteve a Selic em 15,00%.")],
    )


def test_extraction_result():
    anchor = FactualAnchor(id="A01", claim="Selic mantida", numbers=["15,00%"], source_excerpt="manteve a Selic em 15,00%", page=1)
    result = ExtractionResult(key_points=["Selic mantida"], anchors=[anchor])
    assert result.anchors[0].page == 1


def test_generated_content_formats():
    article = GeneratedContent(
        audience=Audience.BEGINNER, format=Format.ARTICLE, attempt=1,
        content=ArticleBody(
            title="Juros parados", subtitle="BC manteve a taxa.",
            sections=[Section(heading="O que houve", body="O Banco Central manteve os juros.", anchor_ids=["A01"])],
        ),
    )
    assert article.content.anchor_ids() == ["A01"]
    assert article.key == "iniciante:texto"

    carousel = CarouselBody(slides=[
        Slide(role="gancho", title="E aí?", text="..."),
        *[Slide(role="corpo", title=f"Ponto {i}", text="...") for i in range(3)],
        Slide(role="conclusao", title="Resumo", text="..."),
    ])
    script = VideoScriptBody(blocks=[
        ScriptBlock(start_s=0, end_s=5, visual_hook="Texto na tela", speech="Os juros não mudaram."),
        ScriptBlock(start_s=5, end_s=55, visual_hook="Gráfico", speech="Veja por quê."),
    ])
    assert GeneratedContent(audience=Audience.ADVANCED, format=Format.CAROUSEL, attempt=1, content=carousel)
    assert GeneratedContent(audience=Audience.ADVANCED, format=Format.VIDEO_SCRIPT, attempt=2, content=script)


def test_format_mismatch_rejected():
    with pytest.raises(ValidationError):
        GeneratedContent(
            audience=Audience.BEGINNER, format=Format.CAROUSEL, attempt=1,
            content=ArticleBody(title="x", subtitle="s", sections=[Section(heading="h", body="y")]),
        )


def test_carousel_requires_hook_and_conclusion():
    with pytest.raises(ValidationError):
        CarouselBody(slides=[Slide(role="corpo", title="a", text="b")] * 5)


@pytest.mark.parametrize("n_body", [2, 7])  # 4 e 9 slides: fora de 5..8
def test_carousel_slide_count(n_body):
    slides = [Slide(role="gancho", title="g", text="t")]
    slides += [Slide(role="corpo", title="c", text="t")] * n_body
    slides += [Slide(role="conclusao", title="f", text="t")]
    with pytest.raises(ValidationError):
        CarouselBody(slides=slides)


def test_carousel_body_slides_only_in_the_middle():
    roles = ["gancho", "corpo", "gancho", "corpo", "conclusao"]
    with pytest.raises(ValidationError):
        CarouselBody(slides=[Slide(role=r, title="t", text="t") for r in roles])


def test_video_script_limit():
    with pytest.raises(ValidationError):
        VideoScriptBody(blocks=[ScriptBlock(start_s=0, end_s=75, visual_hook="x", speech="y")])


def test_metric_direction_and_report():
    flesch = MetricResult(name="flesch_pt", score=62.0, threshold=50.0, direction="min")
    jargon = MetricResult(name="unexplained_terms", score=2, threshold=0, direction="max")
    assert flesch.passed and not jargon.passed
    report = EvaluationReport(audience=Audience.BEGINNER, format=Format.ARTICLE, attempt=1, metrics=[flesch, jargon])
    assert not report.passed
    assert [m.name for m in report.failed_metrics] == ["unexplained_terms"]
    assert report.model_dump()["passed"] is False


def test_graph_state_defaults():
    state = GraphState(document=make_doc())
    assert state.outputs == {} and state.attempts == {} and state.node_log == []
    assert cell_key(Audience.INTERMEDIATE, Format.VIDEO_SCRIPT) == "intermediario:roteiro"
