"""Propõe termos candidatos ao glossário a partir dos documentos processados.

Varre data/processed/*.json com spaCy (noun chunks + entidades), descarta o que
o glossário já cobre e grava os candidatos mais frequentes para revisão humana.

Uso:
    uv run python -m backend.evaluator.mine_terms --top 80
Saída: data/glossary/candidatos.yaml (não altera o glossario.yaml).
"""

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

import spacy
import yaml

from backend.config import GLOSSARY_PATH, PROCESSED_DIR
from backend.evaluator.glossary import SPACY_MODEL, TermMatcher, load_glossary
from backend.schemas import SourceDocument

# Lemas que indicam vocabulário financeiro/econômico (filtro de ruído).
FINANCE_LEMMAS = {
    "taxa", "juro", "inflação", "preço", "crédito", "capital", "lucro", "margem", "dívida", "receita",
    "despesa", "provisão", "carteira", "ativo", "passivo", "patrimônio", "resultado", "câmbio", "política",
    "monetário", "fiscal", "expectativa", "risco", "índice", "spread", "dividendo", "provento", "ação",
    "emissão", "rentabilidade", "retorno", "custo", "inadimplência", "liquidez", "basileia", "guidance",
    "projeção", "meta", "atividade", "demanda", "oferta", "salário", "serviço", "commodity", "tesouro",
}
ACRONYM_RE = re.compile(r"^[A-Z][A-Z0-9]{1,6}$")
STRIP_POS = {"DET", "ADP", "PRON", "NUM", "PUNCT", "CCONJ", "SCONJ"}


def _clean_span(span) -> str | None:
    tokens = list(span)
    while tokens and (tokens[0].pos_ in STRIP_POS or tokens[0].is_stop):
        tokens = tokens[1:]
    while tokens and (tokens[-1].pos_ in STRIP_POS or tokens[-1].is_stop):
        tokens = tokens[:-1]
    if not 1 <= len(tokens) <= 4 or any(t.like_num or t.is_punct for t in tokens):
        return None
    text = " ".join(t.text for t in tokens)
    lemmas = {t.lemma_.lower() for t in tokens}
    if ACRONYM_RE.match(text) or lemmas & FINANCE_LEMMAS:
        return text if ACRONYM_RE.match(text) else text.lower()
    return None


def mine(docs: list[SourceDocument], top: int) -> list[dict]:
    nlp = spacy.load(SPACY_MODEL)
    nlp.max_length = max(nlp.max_length, max(len(d.text) for d in docs) + 1)
    matcher = TermMatcher(load_glossary(GLOSSARY_PATH))
    counts: Counter[str] = Counter()
    seen_in: defaultdict[str, set[str]] = defaultdict(set)
    example: dict[str, str] = {}

    for doc in docs:
        parsed = nlp(doc.text)
        for span in [*parsed.noun_chunks, *parsed.ents]:
            term = _clean_span(span)
            if not term:
                continue
            counts[term] += 1
            seen_in[term].add(doc.id)
            example.setdefault(term, span.sent.text.strip()[:200])

    covered = {t for t in counts if matcher.find(t)}
    ranked = [t for t, _ in counts.most_common() if t not in covered]
    return [
        {"termo": t, "frequencia": counts[t], "documentos": sorted(seen_in[t]), "exemplo": example[t]}
        for t in ranked[:top]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--top", type=int, default=80)
    parser.add_argument("--output", type=Path, default=GLOSSARY_PATH.parent / "candidatos.yaml")
    args = parser.parse_args()

    docs = [SourceDocument.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted(PROCESSED_DIR.glob("*.json"))]
    if not docs:
        raise SystemExit(f"Nenhum documento em {PROCESSED_DIR}. Rode antes: uv run python -m backend.ingestion.cli")
    candidates = mine(docs, args.top)
    args.output.write_text(yaml.safe_dump(candidates, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"{len(candidates)} candidatos -> {args.output}")


if __name__ == "__main__":
    main()
