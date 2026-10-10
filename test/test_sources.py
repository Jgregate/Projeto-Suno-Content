"""Coletor BCB/CVM com transporte HTTP falso (sem rede)."""

import csv
import io
import json
import zipfile
from datetime import date

import httpx
import pytest

from backend.ingestion.sources import (
    BCB_ATA_DETALHE_URL,
    BCB_ATAS_URL,
    fetch_copom_minutes,
    fetch_material_facts,
    list_material_facts,
    slug,
)

PDF = b"%PDF-1.7 fake"


def _ipe_zip() -> bytes:
    header = ["Nome_Companhia", "Data_Referencia", "Categoria", "Assunto", "Data_Entrega", "Protocolo_Entrega", "Link_Download"]
    rows = [
        ["BCO BRADESCO S.A.", "2026-09-30", "Fato Relevante", "JCP", "2026-09-30", "P1", "https://rad.cvm/doc1"],
        ["BCO BRADESCO S.A.", "2026-10-08", "Fato Relevante", "Recompra", "2026-10-08", "P2", "https://rad.cvm/doc2"],
        ["BCO BRADESCO S.A.", "2026-10-09", "Comunicado ao Mercado", "Outro", "2026-10-09", "P3", "https://rad.cvm/doc3"],
        ["ITAÚ UNIBANCO HOLDING S.A.", "2026-10-01", "Fato Relevante", "Dividendos", "2026-10-01", "P4", "https://rad.cvm/doc4"],
    ]
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(header)
    writer.writerows(rows)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("ipe_cia_aberta_2026.csv", buf.getvalue().encode("latin-1"))
    return out.getvalue()


def handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url.startswith(BCB_ATA_DETALHE_URL):
        n = int(request.url.params["nro_reuniao"])
        body = {"conteudo": [{"nroReuniao": n, "dataReferencia": "2026-09-16", "titulo": f"{n}ª Reunião",
                              "urlPdfAta": f"https://bcb/ata{n}.pdf"}]}
        return httpx.Response(200, text=json.dumps(body))
    if url.startswith(BCB_ATAS_URL):
        return httpx.Response(200, json={"conteudo": [{"nroReuniao": 281}]})
    if url.endswith(".zip"):
        return httpx.Response(200, content=_ipe_zip())
    if "doc" in url or url.endswith(".pdf"):
        return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
    return httpx.Response(404)


@pytest.fixture
def client() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_slug_normalizes_company_names():
    assert slug("ITAÚ UNIBANCO HOLDING S.A.") == "itau-unibanco-holding-s-a"


def test_copom_minutes_saved_with_ingestion_naming(client, tmp_path):
    [path] = fetch_copom_minutes(1, tmp_path, client)
    assert path.name == "ata-copom-2026-09-16.pdf" and path.read_bytes() == PDF


def test_material_facts_filter_category_company_and_order(client):
    facts = list_material_facts(client, 2026, "bradesco")
    assert [f.subject for f in facts] == ["Recompra", "JCP"]  # sem comunicado; mais recente primeiro
    assert facts[0].reference_date == date(2026, 10, 8)
    assert list_material_facts(client, 2026, "itaú")[0].company.startswith("ITAÚ")


def test_material_fact_download_and_name(client, tmp_path):
    [path] = fetch_material_facts("bradesco", 2026, 1, tmp_path, client)
    assert path.name == "fato-relevante-bco-bradesco-s-a-2026-10-08.pdf"


def test_non_pdf_response_is_rejected(tmp_path):
    bad = httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"conteudo": [{"nroReuniao": 1, "dataReferencia": "2026-01-01", "titulo": "x",
                                                          "urlPdfAta": "https://bcb/x.html"}]})))
    with pytest.raises(ValueError, match="não devolveu um PDF"):
        fetch_copom_minutes(1, tmp_path, bad)


def test_unknown_company_raises(client, tmp_path):
    with pytest.raises(LookupError):
        fetch_material_facts("empresa-inexistente", 2026, 1, tmp_path, client)
