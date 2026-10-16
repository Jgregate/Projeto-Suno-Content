"""Gerador baseline "ingênuo" para comparação com o pipeline.

Um único prompt por célula ("resuma este documento para um investidor <nível> no
formato <formato>"), sem extractor, sem âncoras, sem glossário e sem regras de nível.
Usa o mesmo modelo "fast" e os mesmos schemas de formato do pipeline, para que a
única diferença seja a arquitetura.

Uso:
    uv run python -m backend.experiments.baseline --doc <id> [--doc <id2>] [--force]
Saída: outputs/<doc_id>/baseline/<timestamp>.json
"""

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from backend.config import BASELINE_PROMPTS_DIR, OUTPUTS_DIR
from backend.llm import LLMClient, get_llm
from backend.nodes.common import call_llm
from backend.nodes.formatter import BODY_SCHEMA
from backend.prompts import prompts_hash, render
from backend.run import load_document, merge_documents
from backend.schemas import Audience, Format, GeneratedContent, NodeRun, SourceDocument, cell_key

AUDIENCE_LABEL = {Audience.BEGINNER: "iniciante", Audience.INTERMEDIATE: "intermediário", Audience.ADVANCED: "avançado"}
FORMAT_LABEL = {Format.ARTICLE: "texto analítico", Format.CAROUSEL: "carrossel", Format.VIDEO_SCRIPT: "roteiro de vídeo curto"}


class BaselineRecord(BaseModel):
    doc_id: str
    prompt_hash: str
    model: str
    created_at: str
    outputs: dict[str, GeneratedContent]
    node_log: list[NodeRun]
    failures: list[str] = []


def generate_baseline(doc: SourceDocument, llm: LLMClient) -> BaselineRecord:
    def one(cell: tuple[Audience, Format]) -> tuple[str, GeneratedContent | None, NodeRun, str | None]:
        audience, fmt = cell
        key = cell_key(audience, fmt)
        system, user = render(
            "naive", BASELINE_PROMPTS_DIR, audience=AUDIENCE_LABEL[audience], format=FORMAT_LABEL[fmt], document=doc.text
        )
        try:
            body, run = call_llm("baseline", key, llm, BODY_SCHEMA[fmt], system, user)
        except ValueError as exc:
            return key, None, NodeRun(node="baseline", cell=key), f"{key}: {exc}"
        return key, GeneratedContent(audience=audience, format=fmt, attempt=1, content=body), run, None

    cells = [(a, f) for a in Audience for f in Format]
    with ThreadPoolExecutor(max_workers=len(cells)) as pool:
        results = list(pool.map(one, cells))
    return BaselineRecord(
        doc_id=doc.id,
        prompt_hash=prompts_hash(BASELINE_PROMPTS_DIR),
        model=llm.model_id,
        created_at=datetime.now().isoformat(timespec="seconds"),
        outputs={k: out for k, out, _, _ in results if out},
        node_log=[run for _, _, run, _ in results],
        failures=[err for *_, err in results if err],
    )


def latest_baseline(doc_id: str) -> BaselineRecord | None:
    files = sorted((OUTPUTS_DIR / doc_id / "baseline").glob("*.json"))
    return BaselineRecord.model_validate_json(files[-1].read_text(encoding="utf-8")) if files else None


def run_baseline(doc: SourceDocument, llm: LLMClient, force: bool = False) -> tuple[BaselineRecord, Path | None, bool]:
    cached = latest_baseline(doc.id)
    if cached and not force and cached.prompt_hash == prompts_hash(BASELINE_PROMPTS_DIR) and cached.model == llm.model_id:
        return cached, None, True
    record = generate_baseline(doc, llm)
    out_dir = OUTPUTS_DIR / doc.id / "baseline"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return record, path, False


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera as 9 saídas do baseline ingênuo.")
    parser.add_argument("--doc", action="append", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    doc = merge_documents([load_document(d) for d in args.doc])
    record, path, cached = run_baseline(doc, get_llm("fast"), force=args.force)
    calls = [r for r in record.node_log if r.model]
    print(f"{'[cache] ' if cached else ''}{path or 'outputs/' + doc.id + '/baseline'}")
    print(f"saídas: {len(record.outputs)}/9 | tokens: {sum(r.input_tokens for r in calls):,} in + "
          f"{sum(r.output_tokens for r in calls):,} out | US$ {sum(r.cost_usd for r in calls):.4f}")


if __name__ == "__main__":
    main()
