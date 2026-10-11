"""Nó Document Extractor & Anchor (modelo "strong") + validação determinística de números."""

from collections.abc import Callable

from backend.evaluator.glossary import TermMatcher
from backend.evaluator.numbers import missing_numbers, number_index
from backend.llm import LLMClient
from backend.nodes.common import call_llm, warn
from backend.prompts import render
from backend.schemas import ExtractionResult, GraphState


def validate_anchor_numbers(extraction: ExtractionResult, source_text: str) -> list[str]:
    """Marca como inválida toda âncora com número ausente da fonte. Devolve os avisos.

    Âncoras inválidas continuam no resultado (auditáveis), mas os adaptadores
    só recebem `extraction.valid_anchors`.
    """
    index = number_index(source_text)
    warnings = []
    for anchor in extraction.anchors:
        missing = missing_numbers(anchor.numbers, index)
        if missing:
            anchor.valid = False
            anchor.invalid_numbers = missing
            warnings.append(warn(f"Âncora {anchor.id} inválida: número(s) fora da fonte {missing}"))
    return warnings


def make_extractor(llm: LLMClient, matcher: TermMatcher) -> Callable[[GraphState], dict]:
    def extractor(state: GraphState) -> dict:
        doc = state.document
        document = "\n\n".join(f"[p. {p.number}]\n{p.text}" for p in doc.pages)
        system, user = render("extractor", doc_type=doc.doc_type.value, title=doc.title, document=document)
        extraction, run = call_llm("extractor", None, llm, ExtractionResult, system, user)

        warnings = validate_anchor_numbers(extraction, doc.text)
        if not extraction.valid_anchors:
            raise ValueError("Extração sem nenhuma âncora válida: os adaptadores não têm base factual.")

        return {
            "extraction": extraction,
            "doc_terms": [t.termo for t in matcher.terms_in(doc.text)],
            "warnings": warnings,
            "node_log": [run],
        }

    return extractor
