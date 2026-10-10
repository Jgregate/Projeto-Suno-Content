"""Ingestão de PDF: PyMuPDF -> texto limpo -> SourceDocument.

Limpeza aplicada:
1. Lê o texto por blocos (parágrafos) do PyMuPDF.
2. Remove cabeçalhos/rodapés repetidos: blocos nas bordas da página cujo
   texto (com dígitos normalizados) se repete em >= 50% das páginas.
3. Remove números de página isolados.
4. Junta quebras de linha dentro do parágrafo e desfaz hifenização.
"""

import re
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

import pymupdf

from backend.schemas import DocumentType, Page, SourceDocument

EDGE_BLOCKS = 2          # blocos do topo/base de cada página tratados como candidatos
REPEAT_RATIO = 0.5       # fração mínima de páginas para considerar repetido
PAGE_NUMBER_RE = re.compile(r"^(p[aá]g(ina)?\.?\s*)?\d{1,4}(\s*(de|/)\s*\d{1,4})?$", re.IGNORECASE)
DATE_IN_NAME_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _normalize(text: str) -> str:
    """Forma canônica para comparar cabeçalhos: sem dígitos, espaços nem caixa."""
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", text)).strip().lower()


def _clean_block(text: str) -> str:
    """Junta as linhas de um bloco num parágrafo único."""
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)   # desfaz hifenização no fim da linha
    text = re.sub(r"\s*\n\s*", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _page_blocks(page: pymupdf.Page) -> list[str]:
    blocks = page.get_text("blocks", sort=True)
    # bloco = (x0, y0, x1, y1, texto, nº, tipo); tipo 0 = texto
    return [b[4] for b in blocks if b[6] == 0 and b[4].strip()]


def _repeated_edges(pages: list[list[str]]) -> set[str]:
    """Textos normalizados que aparecem nas bordas de muitas páginas."""
    if len(pages) < 2:
        return set()
    counts: Counter[str] = Counter()
    for blocks in pages:
        edges = blocks[:EDGE_BLOCKS] + blocks[-EDGE_BLOCKS:]
        counts.update({_normalize(b) for b in edges})
    min_pages = max(2, int(len(pages) * REPEAT_RATIO))
    return {text for text, n in counts.items() if n >= min_pages}


def infer_doc_type(name: str) -> DocumentType:
    """Infere o tipo pelo nome do arquivo (convenção do data/raw/)."""
    name = unicodedata.normalize("NFKD", name.lower())
    if "copom" in name:
        return DocumentType.COPOM_MINUTES
    if "fato" in name:
        return DocumentType.MATERIAL_FACT
    if "release" in name or "resultado" in name:
        return DocumentType.EARNINGS_RELEASE
    return DocumentType.OTHER


def _date_from_name(name: str) -> date | None:
    match = DATE_IN_NAME_RE.search(name)
    if not match:
        return None
    try:
        return date(*map(int, match.groups()))
    except ValueError:
        return None


def load_pdf(path: str | Path, doc_type: DocumentType | None = None) -> SourceDocument:
    """Lê um PDF e devolve um SourceDocument com texto limpo e páginas."""
    path = Path(path)
    with pymupdf.open(path) as pdf:
        raw_pages = [_page_blocks(page) for page in pdf]
        meta_title = (pdf.metadata or {}).get("title", "").strip()

    repeated = _repeated_edges(raw_pages)
    pages: list[Page] = []
    for number, blocks in enumerate(raw_pages, start=1):
        kept = [
            _clean_block(b)
            for b in blocks
            if _normalize(b) not in repeated and not PAGE_NUMBER_RE.match(b.strip())
        ]
        text = "\n\n".join(p for p in kept if p)
        if text:
            pages.append(Page(number=number, text=text))

    if not pages:
        raise ValueError(f"Nenhum texto extraído de {path.name} (PDF escaneado? precisa de OCR).")

    return SourceDocument(
        id=re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-"),
        doc_type=doc_type or infer_doc_type(path.stem),
        title=meta_title or pages[0].text.split("\n\n")[0][:200],
        date=_date_from_name(path.stem),
        text="\n\n".join(p.text for p in pages),
        pages=pages,
        source_path=str(path),
    )
