"""Glossário financeiro: carregamento, validação e casamento de termos por lema (spaCy)."""

import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import spacy
import yaml
from pydantic import BaseModel, Field, field_validator
from spacy.language import Language

from backend.config import GLOSSARY_PATH
from backend.schemas import Audience

SPACY_MODEL = "pt_core_news_lg"
LEVEL_ORDER = {Audience.BEGINNER: 0, Audience.INTERMEDIATE: 1, Audience.ADVANCED: 2}


class GlossaryTerm(BaseModel):
    """Termo técnico e o nível mínimo em que pode aparecer sem explicação."""

    termo: str = Field(min_length=1)
    variacoes: list[str] = Field(default_factory=list)
    nivel_minimo: Audience
    analogia_iniciante: str = Field(min_length=1)
    status: Literal["revisado", "pendente_revisao"] = "revisado"

    @property
    def surface_forms(self) -> list[str]:
        """Termo + variações, para o matcher."""
        return [self.termo, *self.variacoes]

    def needs_explanation_for(self, audience: Audience) -> bool:
        """True se o termo exige explicação/analogia para esse nível."""
        return LEVEL_ORDER[audience] < LEVEL_ORDER[self.nivel_minimo]


class Glossary(BaseModel):
    termos: list[GlossaryTerm] = Field(min_length=1)

    @field_validator("termos")
    @classmethod
    def _no_duplicate_forms(cls, terms: list[GlossaryTerm]) -> list[GlossaryTerm]:
        seen: dict[str, str] = {}
        for term in terms:
            for form in term.surface_forms:
                key = form.casefold()
                if key in seen and seen[key] != term.termo:
                    raise ValueError(f"'{form}' aparece em '{seen[key]}' e em '{term.termo}'.")
                seen[key] = term.termo
        return terms

    def get(self, termo: str) -> GlossaryTerm:
        return next(t for t in self.termos if t.termo == termo)


def load_glossary(path: str | Path = GLOSSARY_PATH) -> Glossary:
    with open(path, encoding="utf-8") as f:
        return Glossary.model_validate(yaml.safe_load(f))


_NLP_LOCK = threading.Lock()


@lru_cache
def get_nlp() -> Language:
    """spaCy só com o necessário para lematizar (sem parser e NER)."""
    return spacy.load(SPACY_MODEL, exclude=["parser", "ner"])


def _tokens(text: str) -> list[tuple[str, str]]:
    """(lema, forma minúscula) de cada token.

    Guardar as duas formas cobre o caso em que o spaCy marca um termo
    capitalizado como nome próprio e não lematiza ("Covenants" -> "covenants").
    """
    with _NLP_LOCK:  # o avaliador roda células em threads; o pipeline spaCy não é thread-safe
        doc = get_nlp()(text)
    return [(t.lemma_.casefold(), t.lower_) for t in doc if not t.is_space]


@dataclass(frozen=True)
class TermMatch:
    termo: str
    start: int  # índice de token
    end: int


class TermMatcher:
    """Casa formas do glossário por sequência de lemas; match mais longo vence."""

    def __init__(self, glossary: Glossary) -> None:
        self.glossary = glossary
        # cada forma vira 2 padrões (lemas e minúsculas), indexados pelo 1º elemento
        self._patterns: dict[str, list[tuple[tuple[str, ...], str]]] = {}
        for term in glossary.termos:
            for form in term.surface_forms:
                toks = _tokens(form)
                for pattern in {tuple(t[0] for t in toks), tuple(t[1] for t in toks)}:
                    if pattern:
                        self._patterns.setdefault(pattern[0], []).append((pattern, term.termo))

    @staticmethod
    def _matches_at(tokens: list[tuple[str, str]], i: int, pattern: tuple[str, ...]) -> bool:
        window = tokens[i : i + len(pattern)]
        return len(window) == len(pattern) and all(p in tok for p, tok in zip(pattern, window, strict=True))

    def find(self, text: str) -> list[TermMatch]:
        tokens = _tokens(text)
        matches: list[TermMatch] = []
        i = 0
        while i < len(tokens):
            candidates = self._patterns.get(tokens[i][0], []) + self._patterns.get(tokens[i][1], [])
            candidates.sort(key=lambda p: len(p[0]), reverse=True)
            for pattern, termo in candidates:
                if self._matches_at(tokens, i, pattern):
                    matches.append(TermMatch(termo, i, i + len(pattern)))
                    i += len(pattern)
                    break
            else:
                i += 1
        return matches

    def terms_in(self, text: str) -> list[GlossaryTerm]:
        """Termos distintos presentes no texto, na ordem da primeira ocorrência."""
        names = dict.fromkeys(m.termo for m in self.find(text))
        return [self.glossary.get(n) for n in names]
