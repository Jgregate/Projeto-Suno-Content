"""Utilidades de texto determinísticas: frases, palavras e sílabas (PT-BR)."""

import re
from functools import lru_cache

import pyphen

# Abreviações comuns em texto financeiro que não encerram frase.
ABBREVIATIONS = ["a.a.", "a.m.", "p.p.", "p.b.", "Sr.", "Sra.", "Dr.", "etc.", "ex.", "nº.", "S.A.", "Ltda."]
_ABBR_RE = re.compile("|".join(re.escape(a) for a in ABBREVIATIONS))
_SENTENCE_END_RE = re.compile(r"(?<=[.!?…])\s+|\n+")
WORD_RE = re.compile(r"\d+(?:[.,]\d+)*%?|[^\W\d_]+(?:[-'][^\W\d_]+)*")
NUMBER_TOKEN_RE = re.compile(r"^\d")


def split_sentences(text: str) -> list[str]:
    """Frases por pontuação final ou quebra de linha (títulos e slides contam como frase)."""
    protected = _ABBR_RE.sub(lambda m: m.group(0).replace(".", "․"), text)
    parts = (p.replace("․", ".").strip() for p in _SENTENCE_END_RE.split(protected))
    return [p for p in parts if WORD_RE.search(p)]


def words(text: str) -> list[str]:
    """Palavras e números ("13,75%" = 1 token)."""
    return WORD_RE.findall(text)


@lru_cache
def _dic() -> pyphen.Pyphen:
    # left/right=1: separa sílabas de 1 letra nas pontas ("á-gua", "e-co-no-mi-a").
    return pyphen.Pyphen(lang="pt_BR", left=1, right=1)


@lru_cache(maxsize=50_000)
def syllables(word: str) -> int:
    """Sílabas por hifenização pt_BR. Aproximação: ditongos/hiatos raros podem errar por 1."""
    return max(1, len(_dic().positions(word.lower())) + 1)


def is_number(token: str) -> bool:
    return bool(NUMBER_TOKEN_RE.match(token))
