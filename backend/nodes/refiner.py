"""Nó Refiner: reescreve só as células reprovadas usando o feedback do avaliador."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from backend.evaluator.glossary import Glossary
from backend.llm import LLMClient
from backend.nodes.adapter import glossary_hints
from backend.nodes.common import call_llm_with_fallback, warn
from backend.nodes.formatter import BODY_SCHEMA, check_script
from backend.prompts import load_text, render
from backend.schemas import GeneratedContent, GraphState, NodeRun, VideoScriptBody


def make_refiner(llm: LLMClient, glossary: Glossary, fallback: LLMClient | None = None) -> Callable[[GraphState], dict]:
    def refine_one(state: GraphState, key: str) -> tuple[str, GeneratedContent | None, NodeRun, list[str]]:
        previous = state.outputs[key]
        report = state.reports[key][-1]
        audience, fmt = previous.audience, previous.format
        anchors = state.extraction.valid_anchors if state.extraction else []
        system, user = render(
            "refiner",
            level_rules=load_text(f"rules_{audience.value}"),  # regras do nível real, mesmo com force_drift
            audience=audience.value,
            format=fmt.value,
            feedback=report.feedback or "(sem feedback textual)",
            failed=", ".join(m.name for m in report.failed_metrics) or "nenhuma",
            passed=", ".join(m.name for m in report.metrics if m.passed) or "nenhuma",
            anchors="\n".join(f"[{a.id}] {a.claim} (números: {', '.join(a.numbers) or '—'})" for a in anchors),
            glossary_hints=glossary_hints(audience, [glossary.get(t) for t in state.doc_terms]),
            previous=previous.content.model_dump_json(indent=1),
        )
        attempt = previous.attempt + 1
        try:
            body, run, notice = call_llm_with_fallback("refiner", key, llm, fallback, BODY_SCHEMA[fmt], system, user)
        except ValueError as exc:
            return key, None, NodeRun(node="refiner", cell=key, attempt=attempt), [warn(f"[{key}] refiner falhou: {exc}")]
        run.attempt = attempt
        issues = check_script(body) if isinstance(body, VideoScriptBody) else []
        content = GeneratedContent(
            audience=audience, format=fmt, attempt=attempt, content=body,
            anchor_ids=list(dict.fromkeys(body.anchor_ids())), warnings=issues,
        )
        return key, content, run, [*([notice] if notice else []), *(warn(f"[{key}] {i}") for i in issues)]

    def refiner(state: GraphState) -> dict:
        with ThreadPoolExecutor(max_workers=max(1, len(state.to_refine))) as pool:
            results = list(pool.map(lambda k: refine_one(state, k), state.to_refine))
        outputs = {k: c for k, c, _, _ in results if c}
        failed = [k for k, c, _, _ in results if c is None]
        return {
            "outputs": outputs,
            # célula cujo refino falhou não volta ao avaliador: encerra com a melhor tentativa
            "warnings": [w for *_, ws in results for w in ws],
            "node_log": [r for _, _, r, _ in results],
            "to_refine": failed,  # o avaliador lê isso para fechar essas células
        }

    return refiner
