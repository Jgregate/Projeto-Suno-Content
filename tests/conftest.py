from pathlib import Path

import pymupdf
import pytest

HEADER = "BANCO CENTRAL DO BRASIL - Documento de teste"
FOOTER = "Uso público"


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """PDF sintético de 3 páginas com cabeçalho, rodapé e nº de página repetidos."""
    path = tmp_path / "ata-copom-teste-2026-09-17.pdf"
    doc = pymupdf.open()
    bodies = [
        "O Comitê decidiu manter a taxa Selic em 15,00% a.a. A decisão é com-\npatível com a convergência da inflação.",
        "O cenário externo segue incerto.\nAs expectativas de inflação seguem desancoradas.",
        "O Comitê avaliará os próximos passos com cautela.",
    ]
    for i, body in enumerate(bodies, start=1):
        page = doc.new_page()
        page.insert_text((72, 50), HEADER, fontsize=9)
        page.insert_text((72, 200), body, fontsize=11)
        page.insert_text((72, 780), FOOTER, fontsize=9)
        page.insert_text((500, 780), str(i), fontsize=9)
    doc.save(path)
    doc.close()
    return path
