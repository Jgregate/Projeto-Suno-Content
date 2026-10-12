"""Exporta o schema OpenAPI para o frontend gerar o cliente TypeScript.

    uv run python -m backend.api.export_openapi
"""

import json

from backend.api.main import app
from backend.config import ROOT_DIR

OUT = ROOT_DIR / "frontend" / "openapi.json"


def main() -> None:
    OUT.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{OUT} ({len(app.openapi()['paths'])} rotas)")


if __name__ == "__main__":
    main()
