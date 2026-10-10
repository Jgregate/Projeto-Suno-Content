"""Processa todos os PDFs de data/raw/ e salva o texto limpo em data/processed/<id>.json.

Uso:
    uv run python -m backend.ingestion.cli
    uv run python -m backend.ingestion.cli --input data/raw --output data/processed
"""

import argparse
import sys
from pathlib import Path

from backend.config import PROCESSED_DIR, RAW_DIR
from backend.ingestion.pdf import load_pdf


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=RAW_DIR)
    parser.add_argument("--output", type=Path, default=PROCESSED_DIR)
    args = parser.parse_args()

    pdfs = sorted(args.input.glob("*.pdf"))
    if not pdfs:
        print(f"Nenhum PDF em {args.input}")
        return 1

    args.output.mkdir(parents=True, exist_ok=True)
    failures = 0
    for pdf in pdfs:
        try:
            doc = load_pdf(pdf)
        except Exception as exc:  # um PDF ruim não deve parar o lote
            failures += 1
            print(f"[erro] {pdf.name}: {exc}")
            continue
        out = args.output / f"{doc.id}.json"
        out.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        print(f"[ok] {pdf.name} -> {out.name} | {doc.doc_type} | {len(doc.pages)} págs | {len(doc.text):,} chars")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
