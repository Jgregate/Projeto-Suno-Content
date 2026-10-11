"""Domain Term Density Score.

- Termos do glossário casados por lema (spaCy) e variações cadastradas.
- Densidade = ocorrências de termos técnicos por 100 palavras.
- Contextualização: termo cujo `nivel_minimo` é superior ao nível do texto precisa
  de explicação/analogia na mesma frase, na anterior (marcadores como "ou seja",
  "funciona como", parênteses) ou na frase seguinte quando ela retoma o termo por
  anáfora ("... lucro recorrente. Esse lucro mostra que ...").
"""

import re
from dataclasses import dataclass, field

from backend.evaluator.glossary import TermMatcher
from backend.evaluator.text import split_sentences, words
from backend.schemas import Audience

# (nome do marcador, regex). A ordem define qual é registrado quando há mais de um.
CONTEXT_MARKERS: list[tuple[str, re.Pattern[str]]] = [
    (name, re.compile(pattern, re.IGNORECASE))
    for name, pattern in [
        ("ou seja", r"\bou seja\b"),
        ("isto é", r"\bisto é\b"),
        ("que é", r"\bque é\b"),
        ("que são", r"\bque são\b"),
        ("funciona como", r"\bfunciona(m)? como\b"),
        ("é como", r"\bé como\b"),
        ("como se fosse", r"\bcomo se fosse\b"),
        ("na prática", r"\bna prática\b"),
        ("significa", r"\bsignifica(m)?\b"),
        ("quer dizer", r"\bquer(em)? dizer\b"),
        ("parênteses", r"\([^)]*\w+\s+\w+[^)]*\)"),  # parênteses com 2+ palavras
        ("travessão", r"\s[—–]\s|\s-\s"),
        ("representa", r"\brepresenta(m)?\b"),
    ]
]
# Frase seguinte iniciada por retomada anafórica ("Esse lucro...", "Isso significa...") conta como explicação.
ANAPHORA_RE = re.compile(r"^(ess[ea]s?|isso|ist[oa]|est[ea]s?|ou seja|em outras palavras|na prática)\b", re.IGNORECASE)
ANAPHORA = "frase seguinte (anáfora)"


@dataclass
class TermOccurrence:
    termo: str
    sentence_index: int
    sentence: str
    needs_context: bool
    marker: str | None = None  # marcador encontrado, se precisava de contexto

    @property
    def contextualized(self) -> bool:
        return not self.needs_context or self.marker is not None


@dataclass
class TermDensity:
    words: int
    occurrences: list[TermOccurrence] = field(default_factory=list)

    @property
    def density(self) -> float:
        """Ocorrências por 100 palavras."""
        return round(100 * len(self.occurrences) / self.words, 2) if self.words else 0.0

    @property
    def needing_context(self) -> list[TermOccurrence]:
        return [o for o in self.occurrences if o.needs_context]

    @property
    def context_pct(self) -> float:
        """% contextualizados entre os que precisavam de contexto (100 se nenhum precisava)."""
        needing = self.needing_context
        if not needing:
            return 100.0
        return round(100 * sum(o.contextualized for o in needing) / len(needing), 2)

    @property
    def uncontextualized(self) -> list[TermOccurrence]:
        return [o for o in self.needing_context if not o.contextualized]


def find_marker(text: str) -> str | None:
    return next((name for name, rx in CONTEXT_MARKERS if rx.search(text)), None)


def context_marker(sentences: list[str], i: int) -> str | None:
    """Explicação do termo da frase `i`: na própria frase, na anterior ou na seguinte (por anáfora)."""
    if marker := find_marker(sentences[i]):
        return marker
    if i > 0 and (marker := find_marker(sentences[i - 1])):
        return marker
    if i + 1 < len(sentences) and ANAPHORA_RE.match(sentences[i + 1].lstrip("\"'“ ")):
        return ANAPHORA
    return None


def term_density(text: str, audience: Audience, matcher: TermMatcher) -> TermDensity:
    sentences = split_sentences(text)
    result = TermDensity(words=len(words(text)))
    for i, sentence in enumerate(sentences):
        for match in matcher.find(sentence):
            term = matcher.glossary.get(match.termo)
            needs = term.needs_explanation_for(audience)
            marker = context_marker(sentences, i) if needs else None
            result.occurrences.append(TermOccurrence(term.termo, i, sentence, needs, marker))
    return result
