from datetime import date

import pytest

from backend.config import RAW_DIR
from backend.ingestion.pdf import load_pdf
from backend.schemas import DocumentType
from tests.conftest import FOOTER, HEADER


def test_load_sample_pdf(sample_pdf):
    doc = load_pdf(sample_pdf)
    assert doc.text.strip()
    assert len(doc.pages) == 3
    assert doc.doc_type == DocumentType.COPOM_MINUTES
    assert doc.date == date(2026, 9, 17)


def test_removes_repeated_header_footer_and_page_numbers(sample_pdf):
    doc = load_pdf(sample_pdf)
    assert HEADER not in doc.text
    assert FOOTER not in doc.text
    assert all(not line.strip().isdigit() for line in doc.text.splitlines())


def test_joins_lines_and_dehyphenates(sample_pdf):
    doc = load_pdf(sample_pdf)
    assert "compatível" in doc.text
    assert "15,00% a.a." in doc.text


REAL_PDFS = sorted(RAW_DIR.glob("*.pdf"))


@pytest.mark.skipif(not REAL_PDFS, reason="Nenhum PDF real em data/raw/")
@pytest.mark.parametrize("pdf", REAL_PDFS, ids=lambda p: p.name)
def test_real_pdfs_have_text(pdf):
    doc = load_pdf(pdf)
    assert len(doc.text) > 500
