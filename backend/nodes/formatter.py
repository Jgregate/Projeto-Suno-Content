"""Format Synthesizers: um nó por célula nível x formato (modelo "fast")."""

from collections.abc import Callable

from backend.llm import LLMClient
from backend.nodes.common import call_llm_with_fallback, warn
from backend.prompts import load_text, render
from backend.schemas import (
    ArticleBody,
    Audience,
    CarouselBody,
    Format,
    GeneratedContent,
    GraphState,
    NodeRun,
    VideoScriptBody,
    cell_key,
)
from backend.schemas.content import MAX_SCRIPT_WORDS

BODY_SCHEMA: dict[Format, type[ArticleBody | CarouselBody | VideoScriptBody]] = {
    Format.ARTICLE: ArticleBody,
    Format.CAROUSEL: CarouselBody,
    Format.VIDEO_SCRIPT: VideoScriptBody,
}
HOOK_MAX_SECONDS = 3


def check_script(body: VideoScriptBody) -> list[str]:
    """Checagens do roteiro que só registram (não rejeitam a saída)."""
    issues = []
    if body.word_count > MAX_SCRIPT_WORDS:
        issues.append(f"roteiro com {body.word_count} palavras de fala (limite {MAX_SCRIPT_WORDS})")
    if body.blocks[0].end_s > HOOK_MAX_SECONDS:
        issues.append(f"gancho termina em {body.blocks[0].end_s:g}s (esperado até {HOOK_MAX_SECONDS}s)")
    return issues


def make_formatter(
    audience: Audience, fmt: Format, llm: LLMClient, fallback: LLMClient | None = None
) -> Callable[[GraphState], dict]:
    key = cell_key(audience, fmt)

    def formatter(state: GraphState) -> dict:
        adapted = state.adapted[audience.value]
        rules_level = Audience.ADVANCED if state.force_drift == audience else audience  # ver force_drift no adapter
        system, user = render(
            f"format_{fmt.value}",
            level_rules=load_text(f"rules_{rules_level.value}"),
            audience=rules_level.value,
            angle=adapted.angle,
            claims="\n".join(f"- {c.text} [{', '.join(c.anchor_ids)}]" for c in adapted.claims),
            takeaway=adapted.takeaway,
        )
        try:
            body, run, notice = call_llm_with_fallback("formatter", key, llm, fallback, BODY_SCHEMA[fmt], system, user)
        except ValueError as exc:  # sem saída válida nem no fallback: a célula é descartada, a execução continua
            return {"warnings": [warn(f"[{key}] falhou: {exc}")], "node_log": [NodeRun(node="formatter", cell=key)]}

        known = {a.id for a in state.extraction.valid_anchors} if state.extraction else set()
        anchor_ids = list(dict.fromkeys(body.anchor_ids()))
        issues = check_script(body) if isinstance(body, VideoScriptBody) else []
        if unknown := sorted(set(anchor_ids) - known):
            issues.append(f"cita âncoras inexistentes/inválidas {unknown}")

        content = GeneratedContent(
            audience=audience,
            format=fmt,
            attempt=state.attempts.get(key, 0) + 1,
            content=body,
            anchor_ids=anchor_ids,
            warnings=issues,
        )
        return {
            "outputs": {key: content},
            "warnings": [*([notice] if notice else []), *(warn(f"[{key}] {i}") for i in issues)],
            "node_log": [run],
        }

    return formatter
