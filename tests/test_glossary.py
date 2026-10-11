from backend.evaluator.glossary import load_glossary
from backend.schemas import Audience


def test_glossary_loads():
    glossary = load_glossary()
    assert len(glossary.termos) >= 20
    assert all(t.analogia_iniciante for t in glossary.termos)


def test_glossary_has_expected_terms():
    terms = {t.termo: t for t in load_glossary().termos}
    assert terms["Selic"].nivel_minimo == Audience.INTERMEDIATE
    assert terms["hiato do produto"].nivel_minimo == Audience.ADVANCED


def test_matcher_uses_lemmas_and_longest_match():
    from backend.evaluator.glossary import TermMatcher

    matcher = TermMatcher(load_glossary())
    text = "As taxas terminais subiram. O EBITDA ajustado caiu, mas o EBITDA subiu. Covenants foram revistos."
    assert [t.termo for t in matcher.terms_in(text)] == ["taxa terminal", "EBITDA ajustado", "EBITDA", "covenants"]


def test_needs_explanation_by_level():
    terms = {t.termo: t for t in load_glossary().termos}
    assert terms["Selic"].needs_explanation_for(Audience.BEGINNER)
    assert not terms["Selic"].needs_explanation_for(Audience.INTERMEDIATE)
    assert terms["covenants"].needs_explanation_for(Audience.INTERMEDIATE)
    assert not terms["covenants"].needs_explanation_for(Audience.ADVANCED)


def test_glossary_size_and_pending_status():
    glossary = load_glossary()
    pending = [t for t in glossary.termos if t.status == "pendente_revisao"]
    assert 80 <= len(glossary.termos) <= 110
    assert pending and all(t.analogia_iniciante for t in pending)
