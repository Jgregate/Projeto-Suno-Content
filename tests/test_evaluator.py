"""Testes do Avaliador Híbrido: determinismo, golden tests e partes unitárias."""

from pathlib import Path

import pytest

from backend.evaluator.glossary import TermMatcher, load_glossary
from backend.evaluator.hybrid import HybridEvaluator
from backend.evaluator.level_classifier import predict_level
from backend.evaluator.numbers import ungrounded_quantities
from backend.evaluator.readability import readability
from backend.evaluator.term_density import ANAPHORA, context_marker, find_marker, term_density
from backend.evaluator.text import split_sentences, syllables
from backend.schemas import Audience, Format, MetricResult, Page, SourceDocument

GOLDEN = Path(__file__).parent / "fixtures" / "golden"


def golden(name: str) -> str:
    return (GOLDEN / f"{name}.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def matcher() -> TermMatcher:
    return TermMatcher(load_glossary())


@pytest.fixture(scope="module")
def evaluator(matcher) -> HybridEvaluator:
    return HybridEvaluator(matcher)  # só determinístico


@pytest.fixture(scope="module")
def source() -> SourceDocument:
    text = golden("fonte_copom")
    return SourceDocument(id="fonte-copom", title="Fonte", text=text, pages=[Page(number=1, text=text)])


def evaluate(evaluator, source, name: str, audience: Audience, fmt: Format = Format.ARTICLE):
    return evaluator.evaluate_text(golden(name), audience, fmt, source)


# --- sílabas, frases ---

@pytest.mark.parametrize(
    "word, n",
    [("casa", 2), ("juros", 2), ("inflação", 3), ("pássaro", 3), ("água", 2), ("economia", 5),
     ("país", 2), ("saída", 3), ("ideia", 3), ("criança", 3), ("mais", 1), ("política", 4), ("taxa", 2)],
)
def test_syllables_known_words(word, n):
    assert syllables(word) == n


def test_syllables_known_limitation():
    # Hiato final "-ria" é lido como ditongo pelo dicionário de hifenização: mo-ne-tá-ria (4, gramática diz 5).
    # Erra para menos em palavras longas -> Flesch levemente otimista. Documentado no README.
    assert syllables("monetária") == 4


def test_abbreviations_do_not_split_sentences():
    assert split_sentences("A Selic foi a 13,75% a.a. no fim. Depois caiu 0,5 p.p. de novo.") == [
        "A Selic foi a 13,75% a.a. no fim.", "Depois caiu 0,5 p.p. de novo."
    ]


def test_flesch_formula_by_hand():
    r = readability("Casa boa. Mesa nova.")  # 4 palavras, 2 frases, 8 sílabas
    assert r.words_per_sentence == 2 and r.syllables_per_word == 2
    assert r.flesch_pt == round(248.835 - 1.015 * 2 - 84.6 * 2, 2)


def test_short_text_is_low_reliability():
    assert readability("Texto curto.").low_reliability
    assert not readability(golden("iniciante_bom")).low_reliability


# --- determinismo ---

def test_same_input_same_scores(evaluator, source):
    runs = [evaluate(evaluator, source, "intermediario_hiato", Audience.INTERMEDIATE) for _ in range(3)]
    dumps = [r.report.model_dump() for r in runs]
    assert dumps[0] == dumps[1] == dumps[2]


# --- golden tests ---

def test_good_beginner_text_passes_beginner(evaluator, source):
    ev = evaluate(evaluator, source, "iniciante_bom", Audience.BEGINNER)
    assert ev.report.passed, ev.report.feedback
    assert ev.predicted_level == Audience.BEGINNER


def test_copom_excerpt_fails_beginner(evaluator, source):
    ev = evaluate(evaluator, source, "copom_trecho", Audience.BEGINNER)
    failed = {m.name for m in ev.report.failed_metrics}
    assert {"flesch_pt", "term_density", "term_context_pct"} <= failed
    assert "Flesch" in ev.report.feedback and "encurte" in ev.report.feedback
    assert ev.predicted_level == Audience.ADVANCED


def test_unexplained_output_gap_is_flagged(evaluator, source):
    ev = evaluate(evaluator, source, "intermediario_hiato", Audience.INTERMEDIATE)
    unexplained = [o.termo for o in ev.terms.uncontextualized]
    assert unexplained == ["hiato do produto"]
    assert not ev.report.metric("term_context_pct").passed
    assert "'hiato do produto' sem explicação na frase 4" in ev.report.feedback


def test_explained_term_records_marker(evaluator, source):
    ev = evaluate(evaluator, source, "intermediario_bom", Audience.INTERMEDIATE)
    hiato = next(o for o in ev.terms.occurrences if o.termo == "hiato do produto")
    assert hiato.marker == "ou seja"


def test_invented_number_fails_factuality(evaluator, source):
    ev = evaluate(evaluator, source, "iniciante_numero_inventado", Audience.BEGINNER)
    assert ev.ungrounded == ["16,5"]
    assert not ev.report.metric("numeric_grounding").passed and not ev.report.passed
    assert "Alucinação numérica: 16,5" in ev.report.feedback


def test_trivialized_advanced_text_fails_min_density(evaluator, source):
    ev = evaluate(evaluator, source, "avancado_trivializado", Audience.ADVANCED)
    m = ev.report.metric("term_density")
    assert m.score < 5 and not m.passed
    assert "trivializado" in ev.report.feedback and "hiato do produto" in ev.report.feedback


def test_good_advanced_text_passes_advanced(evaluator, source):
    ev = evaluate(evaluator, source, "avancado_bom", Audience.ADVANCED)
    assert ev.report.passed, ev.report.feedback
    assert ev.report.metric("flesch_pt").direction == "info"


# --- partes unitárias ---

def test_number_grounding_rounding_and_units():
    src = ["Lucro de R$ 12.407 milhões; Selic de 14,25% para 13,75%; corte de 0,50 p.p."]
    ok = "R$ 12,4 bilhões, mais de R$ 12 bilhões, 13,75%, corte de 50 pontos-base"
    assert ungrounded_quantities(ok, src) == []
    assert ungrounded_quantities("R$ 13,1 bilhões e 15,25%", src) == ["13,1 bilhões", "15,25"]


def test_huge_source_numbers_do_not_break_rounding_check():
    # regressão: "123.456.789.012.345" reescalado por 10^12 estourava a precisão do Decimal no quantize
    assert ungrounded_quantities("12,34", ["123.456.789.012.345"]) == ["12,34"]
    assert ungrounded_quantities("R$ 123,5 trilhões", ["123.456.789.012.345"]) == []


def test_rounding_can_be_turned_off():
    assert ungrounded_quantities("12,4 bilhões", ["12.407 milhões"], rel_tolerance=0, allow_rounding=False) == ["12,4 bilhões"]
    assert ungrounded_quantities("12,4 bilhões", ["12.407 milhões"], rel_tolerance=0.005, allow_rounding=False) == []


@pytest.mark.parametrize(
    "text, marker",
    [("A Selic, ou seja, o juro básico", "ou seja"), ("O CDI (a taxa entre bancos) subiu", "parênteses"),
     ("O hiato — a folga da economia — fechou", "travessão"), ("Funciona como um termostato", "funciona como"),
     ("A carteira representa o dinheiro emprestado", "representa"), ("O hiato do produto ficou positivo", None)],
)
def test_context_markers(text, marker):
    assert find_marker(text) == marker


def test_context_window_previous_same_and_anaphoric_next_sentence():
    sentences = ["O banco teve lucro recorrente de R$ 12,4 bilhões.", "Esse lucro mostra que o negócio ganha sempre.", "O ROE subiu."]
    assert context_marker(sentences, 0) == ANAPHORA          # explicado na frase seguinte ("Esse lucro...")
    assert context_marker(sentences, 2) is None              # frase seguinte não existe; anterior sem marcador
    assert context_marker(["A Selic, ou seja, o juro básico.", "Ela subiu."], 1) == "ou seja"  # frase anterior
    assert context_marker(["O ROE subiu.", "O lucro caiu."], 0) is None  # frase seguinte não retoma o termo


def test_anaphoric_explanation_counts_for_beginner(matcher):
    text = "O banco teve lucro líquido recorrente de R$ 12,4 bilhões. Esse lucro mostra o que o banco ganha sempre."
    td = term_density(text, Audience.BEGINNER, matcher)
    occ = next(o for o in td.occurrences if o.termo == "lucro líquido recorrente")
    assert occ.needs_context and occ.marker == ANAPHORA and td.context_pct == 100.0


def test_density_counts_occurrences_per_100_words(matcher):
    td = term_density("A Selic subiu. O IPCA caiu. " + "palavra " * 16, Audience.ADVANCED, matcher)
    assert td.words == 22 and len(td.occurrences) == 2 and td.density == round(200 / 22, 2)


def test_range_metric():
    assert MetricResult(name="x", score=50, threshold=40, threshold_max=60, direction="range").passed
    assert not MetricResult(name="x", score=65, threshold=40, threshold_max=60, direction="range").passed
    assert MetricResult(name="x", score=-5, direction="info").passed


@pytest.mark.parametrize(
    "flesch, density, expected",
    [(80, 1, Audience.BEGINNER), (50, 4, Audience.INTERMEDIATE), (20, 9, Audience.ADVANCED),
     (55, 0.5, Audience.BEGINNER), (45, 5.5, Audience.INTERMEDIATE)],
)
def test_level_classifier(flesch, density, expected):
    assert predict_level({"flesch_pt": flesch, "term_density": density}) == expected


def test_flesch_feedback_only_asks_to_shorten_long_sentences(evaluator, source):
    # frases já curtas, mas com palavras longas: o feedback não deve mandar encurtar frases
    text = "A desinflação prossegue. As expectativas permanecem desancoradas. O comitê monitora atentamente."
    ev = evaluator.evaluate_text(text, Audience.BEGINNER, Format.ARTICLE, source)
    assert "Flesch" in ev.report.feedback and "encurte" not in ev.report.feedback
    assert "4+ sílabas" in ev.report.feedback


def test_feedback_number_never_looks_equal_to_threshold():
    from backend.evaluator.feedback import _num

    assert _num(39.91) == "39.9" and _num(27.0) == "27" and _num(60.04) == "60"
