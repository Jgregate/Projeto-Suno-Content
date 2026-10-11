"""Legibilidade: Flesch adaptado ao português (Martins et al., 1996).

    Flesch_PT = 248,835 − 1,015 × (palavras/frase) − 84,6 × (sílabas/palavra)

Convenções:
- Frases terminam em pontuação final ou quebra de linha; abreviações como "a.a." e "p.p." não quebram.
- Palavras por frase incluem números ("13,75%" conta como uma palavra).
- Sílabas por palavra e % de polissílabas usam só tokens alfabéticos; contar números como
  monossílabos baixaria a média de sílabas sem o texto ficar mais simples.
- Textos com menos de 100 palavras recebem a flag "baixa_confiabilidade".

O textstat 0.7.x não tem coeficientes para português: com set_lang("pt") usa a constante do
inglês (206,835), cerca de 42 pontos abaixo. A silabação com left/right=2 e a contagem de
números compensam parte da diferença; nos textos golden, o textstat fica ~30 pontos abaixo.
"""

from dataclasses import dataclass

import textstat

from backend.evaluator.text import is_number, split_sentences, syllables, words

MIN_RELIABLE_WORDS = 100
LOW_RELIABILITY = "baixa_confiabilidade"


@dataclass(frozen=True)
class Readability:
    flesch_pt: float
    words: int
    sentences: int
    words_per_sentence: float
    syllables_per_word: float
    pct_polysyllables: float  # % de palavras com 4+ sílabas
    longest_sentences: tuple[str, ...]  # para o feedback

    @property
    def low_reliability(self) -> bool:
        return self.words < MIN_RELIABLE_WORDS


def readability(text: str) -> Readability:
    sentences = split_sentences(text)
    tokens = words(text)
    alpha = [t for t in tokens if not is_number(t)]
    if not sentences or not alpha:
        return Readability(0.0, len(tokens), len(sentences), 0.0, 0.0, 0.0, ())

    syl = [syllables(w) for w in alpha]
    wps = len(tokens) / len(sentences)
    spw = sum(syl) / len(alpha)
    longest = tuple(sorted(sentences, key=lambda s: len(words(s)), reverse=True)[:2])
    return Readability(
        flesch_pt=round(248.835 - 1.015 * wps - 84.6 * spw, 2),
        words=len(tokens),
        sentences=len(sentences),
        words_per_sentence=round(wps, 2),
        syllables_per_word=round(spw, 3),
        pct_polysyllables=round(100 * sum(s >= 4 for s in syl) / len(alpha), 2),
        longest_sentences=longest,
    )


def textstat_flesch_pt(text: str) -> float:
    """Flesch do textstat, usado apenas como comparação no notebook de calibração."""
    textstat.set_lang("pt")
    return round(textstat.flesch_reading_ease(text), 2)
