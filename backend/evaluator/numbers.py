"""Normalização de números no formato brasileiro.

Converte "R$ 12,4 bilhões", "12.407", "24,3%", "-0,5 p.p." em valores
canônicos (Decimal normalizado) para comparar âncoras com o texto-fonte.
Unidade (mi/bi), sinal e símbolo (% / p.p. / R$) são ignorados: a checagem
é "este número aparece na fonte?", não "o valor econômico é idêntico".
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# 1.234.567,89 | 12.407 | 24,3 | 2026 | 0,25
NUMBER_RE = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def _to_decimal(token: str) -> Decimal | None:
    try:
        return Decimal(token.replace(".", "").replace(",", ".")).normalize()
    except InvalidOperation:
        return None


def extract_numbers(text: str) -> list[Decimal]:
    """Todos os números do texto, já normalizados."""
    values = (_to_decimal(t) for t in NUMBER_RE.findall(text))
    return [v for v in values if v is not None]


def number_index(text: str) -> set[Decimal]:
    """Conjunto de números do documento-fonte, para busca O(1)."""
    return set(extract_numbers(text))


def missing_numbers(numbers: list[str], source_index: set[Decimal]) -> list[str]:
    """Strings de `numbers` com algum valor que não aparece na fonte.

    Uma string sem nenhum dígito (ex.: "dois terços") não é checada.
    """
    missing = []
    for raw in numbers:
        values = extract_numbers(raw)
        if values and any(v not in source_index for v in values):
            missing.append(raw)
    return missing


# --- Quantidades com unidade, para o Factuality Checker ---

SCALES = {
    "mil": 3, "milhão": 6, "milhões": 6, "mi": 6, "mm": 6,
    "bilhão": 9, "bilhões": 9, "bi": 9, "bn": 9, "trilhão": 12, "trilhões": 12, "tri": 12,
    # pontos-base -> pontos percentuais: "50 pontos-base" = "0,50 p.p."
    "pontos-base": -2, "pontos base": -2, "ponto-base": -2, "bps": -2, "bp": -2, "p.b.": -2,
}
QUANTITY_RE = re.compile(
    rf"(?P<num>{NUMBER_RE.pattern})(?:\s*(?P<unit>{'|'.join(re.escape(u) for u in sorted(SCALES, key=len, reverse=True))})(?!\w))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Quantity:
    raw: str
    value: Decimal       # valor como escrito ("12,4" -> 12.4)
    exponent: int        # potência de 10 da unidade (bilhões -> 9)
    decimals: int        # casas decimais escritas ("12,40" -> 2)


def extract_quantities(text: str) -> list[Quantity]:
    out = []
    for m in QUANTITY_RE.finditer(text):
        value = _to_decimal(m.group("num"))
        if value is None:
            continue
        num = m.group("num")
        decimals = len(num.split(",", 1)[1]) if "," in num else 0
        unit = (m.group("unit") or "").lower()
        out.append(Quantity(m.group(0).strip(), value, SCALES.get(unit, 0), decimals))
    return out


def _rounds_to(source: Decimal, target: Quantity) -> bool:
    quantum = Decimal(1).scaleb(-target.decimals)
    try:
        return source.quantize(quantum, rounding=ROUND_HALF_UP) == target.value.quantize(quantum)
    except InvalidOperation:  # reescala acima da precisão do contexto Decimal
        return False


def is_grounded(q: Quantity, sources: list[Quantity], rel_tolerance: float, allow_rounding: bool) -> bool:
    """True se `q` corresponde a algum número da fonte.

    Compara em todas as escalas de mil (10^-12 a 10^12), porque tabelas de release
    costumam omitir a unidade ("12.407" sob o cabeçalho "R$ milhões"):
    "R$ 12.407 milhões" ≈ "R$ 12,4 bilhões" ≈ "12.407" (tabela).
    Aceita: igualdade, diferença relativa <= rel_tolerance, ou arredondamento
    do valor-fonte para as casas decimais escritas em `q` (se allow_rounding).
    """
    tol = Decimal(str(rel_tolerance))
    for s in sources:
        base = s.value.scaleb(s.exponent - q.exponent)
        for shift in range(-12, 13, 3):
            candidate = base.scaleb(shift) if shift else base
            if candidate == q.value:
                return True
            if candidate and abs(candidate - q.value) <= tol * abs(candidate):
                return True
            if allow_rounding and _rounds_to(candidate, q):
                return True
    return False


def ungrounded_quantities(
    text: str, source_texts: list[str], rel_tolerance: float = 0.005, allow_rounding: bool = True
) -> list[str]:
    """Números do texto gerado sem correspondência na fonte (alucinação numérica)."""
    sources = [q for t in source_texts for q in extract_quantities(t)]
    return [q.raw for q in extract_quantities(text) if not is_grounded(q, sources, rel_tolerance, allow_rounding)]
