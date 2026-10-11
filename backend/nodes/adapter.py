"""Audience Adapters: um nó por nível (modelo "fast"), rodando em paralelo."""

from collections.abc import Callable

from backend.evaluator.glossary import Glossary, GlossaryTerm
from backend.llm import LLMClient
from backend.nodes.common import call_llm, warn
from backend.prompts import load_text, render
from backend.schemas import AdaptedContent, Audience, GraphState


def glossary_hints(audience: Audience, terms: list[GlossaryTerm]) -> str:
    """Orientação por termo encontrado no documento, de acordo com o nível."""
    if not terms:
        return "(nenhum)"
    lines = []
    for term in terms:
        if not term.needs_explanation_for(audience):
            lines.append(f"- {term.termo}: pode usar sem explicar.")
        elif audience == Audience.BEGINNER:
            lines.append(f"- {term.termo}: só use com analogia cotidiana. Referência: {term.analogia_iniciante}")
        else:
            lines.append(f"- {term.termo}: jargão institucional; se usar, explique em poucas palavras.")
    return "\n".join(lines)


def make_adapter(audience: Audience, llm: LLMClient, glossary: Glossary) -> Callable[[GraphState], dict]:
    def adapter(state: GraphState) -> dict:
        extraction = state.extraction
        assert extraction is not None, "adapter rodou antes do extractor"
        anchors = extraction.valid_anchors
        # force_drift: o nível usa as regras do Avançado na 1ª tentativa (demonstração do loop)
        rules_level = Audience.ADVANCED if state.force_drift == audience else audience
        system, user = render(
            "adapter",
            level_rules=load_text(f"rules_{rules_level.value}"),
            audience=rules_level.value,
            key_points="\n".join(f"- {p}" for p in extraction.key_points),
            anchors="\n".join(
                f"[{a.id}] {a.claim} (números: {', '.join(a.numbers) or '—'})" for a in anchors
            ),
            glossary_hints=glossary_hints(rules_level, [glossary.get(t) for t in state.doc_terms]),
        )
        adapted, run = call_llm("adapter", audience.value, llm, AdaptedContent, system, user)
        adapted.audience = audience  # o nível vem do nó, não da resposta do modelo

        valid_ids = {a.id for a in anchors}
        warnings = [
            warn(f"[{audience.value}] claim cita âncora inexistente/inválida {sorted(set(c.anchor_ids) - valid_ids)}: {c.text[:60]}")
            for c in adapted.claims
            if not set(c.anchor_ids) <= valid_ids
        ]
        return {"adapted": {audience.value: adapted}, "warnings": warnings, "node_log": [run]}

    return adapter
