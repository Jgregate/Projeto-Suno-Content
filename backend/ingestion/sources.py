"""Coleta de documentos públicos reais direto das fontes oficiais.

- Atas do Copom: API do site do Banco Central (lista de atas + PDF oficial de cada reunião).
- Fatos relevantes: dados abertos da CVM (índice IPE de companhias abertas, com o link de cada PDF).

Os PDFs são salvos em data/raw/ com o nome que a ingestão usa para inferir tipo e data:
    ata-copom-AAAA-MM-DD.pdf
    fato-relevante-<empresa>-AAAA-MM-DD.pdf

Uso:
    uv run python -m backend.ingestion.sources copom --quantidade 1
    uv run python -m backend.ingestion.sources fato-relevante --empresa bradesco --ano 2026 --quantidade 1
    uv run python -m backend.ingestion.sources fato-relevante --empresa itau --listar   # só mostra os candidatos
Depois: uv run python -m backend.ingestion.cli
"""

import argparse
import csv
import io
import re
import sys
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from backend.config import RAW_DIR

BCB_ATAS_URL = "https://www.bcb.gov.br/api/servico/sitebcb/copom/atas"
BCB_ATA_DETALHE_URL = "https://www.bcb.gov.br/api/servico/sitebcb/copom/atas_detalhes"
CVM_IPE_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{ano}.zip"
USER_AGENT = "suno-content/0.1 (projeto academico; coleta de documentos publicos)"
PDF_MAGIC = b"%PDF"


def make_client() -> httpx.Client:
    return httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT})


def slug(text: str) -> str:
    """'BCO BRADESCO S.A.' -> 'bco-bradesco-s-a'."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def _save_pdf(client: httpx.Client, url: str, path: Path) -> Path:
    response = client.get(url)
    response.raise_for_status()
    if not response.content.startswith(PDF_MAGIC):
        raise ValueError(f"{url} não devolveu um PDF (content-type {response.headers.get('content-type')}).")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path


# --- Banco Central: atas do Copom ---

@dataclass(frozen=True)
class CopomMinutes:
    meeting: int
    reference_date: date
    title: str
    pdf_url: str

    @property
    def filename(self) -> str:
        return f"ata-copom-{self.reference_date.isoformat()}.pdf"


def list_copom_minutes(client: httpx.Client, quantity: int = 1) -> list[CopomMinutes]:
    """As `quantity` atas mais recentes, com o link do PDF oficial."""
    response = client.get(BCB_ATAS_URL, params={"quantidade": quantity})
    response.raise_for_status()
    minutes = []
    for item in response.json()["conteudo"]:
        detail = client.get(BCB_ATA_DETALHE_URL, params={"nro_reuniao": item["nroReuniao"]})
        detail.raise_for_status()
        info = detail.json()["conteudo"][0]
        minutes.append(CopomMinutes(
            meeting=int(info["nroReuniao"]),
            reference_date=date.fromisoformat(info["dataReferencia"]),
            title=info["titulo"],
            pdf_url=info["urlPdfAta"],
        ))
    return minutes


def fetch_copom_minutes(quantity: int = 1, out_dir: Path = RAW_DIR, client: httpx.Client | None = None) -> list[Path]:
    client = client or make_client()
    return [_save_pdf(client, m.pdf_url, out_dir / m.filename) for m in list_copom_minutes(client, quantity)]


# --- CVM: fatos relevantes (dados abertos IPE) ---

@dataclass(frozen=True)
class MaterialFact:
    company: str
    reference_date: date
    delivery_date: date
    subject: str
    protocol: str
    url: str

    @property
    def filename(self) -> str:
        return f"fato-relevante-{slug(self.company)[:40].strip('-')}-{self.reference_date.isoformat()}.pdf"


def list_material_facts(client: httpx.Client, year: int, company: str = "") -> list[MaterialFact]:
    """Fatos relevantes do ano no índice IPE da CVM, mais recentes primeiro; `company` filtra pelo nome."""
    response = client.get(CVM_IPE_URL.format(ano=year))
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".csv"))
        rows = list(csv.DictReader(io.TextIOWrapper(archive.open(name), encoding="latin-1"), delimiter=";"))
    wanted = slug(company)
    facts = [
        MaterialFact(
            company=r["Nome_Companhia"].strip(),
            reference_date=date.fromisoformat(r["Data_Referencia"]),
            delivery_date=date.fromisoformat(r["Data_Entrega"]),
            subject=r["Assunto"].strip(),
            protocol=r["Protocolo_Entrega"],
            url=r["Link_Download"],
        )
        for r in rows
        if r["Categoria"] == "Fato Relevante" and r["Link_Download"] and wanted in slug(r["Nome_Companhia"])
    ]
    return sorted(facts, key=lambda f: (f.delivery_date, f.protocol), reverse=True)


def fetch_material_facts(
    company: str, year: int, quantity: int = 1, out_dir: Path = RAW_DIR, client: httpx.Client | None = None
) -> list[Path]:
    client = client or make_client()
    facts = list_material_facts(client, year, company)
    if not facts:
        raise LookupError(f"Nenhum fato relevante de '{company}' em {year} no índice da CVM.")
    return [_save_pdf(client, f.url, out_dir / f.filename) for f in facts[:quantity]]


# --- CLI ---

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Baixa documentos públicos (BCB e CVM) para data/raw/.")
    sub = parser.add_subparsers(dest="fonte", required=True)
    copom = sub.add_parser("copom", help="atas do Copom (Banco Central)")
    copom.add_argument("--quantidade", type=int, default=1)
    fato = sub.add_parser("fato-relevante", help="fatos relevantes (CVM, dados abertos IPE)")
    fato.add_argument("--empresa", required=True, help="parte do nome da companhia (ex.: bradesco)")
    fato.add_argument("--ano", type=int, default=date.today().year)
    fato.add_argument("--quantidade", type=int, default=1)
    fato.add_argument("--listar", action="store_true", help="só lista os candidatos, sem baixar")
    for p in (copom, fato):
        p.add_argument("--saida", type=Path, default=RAW_DIR)
    args = parser.parse_args(argv)

    with make_client() as client:
        if args.fonte == "copom":
            paths = fetch_copom_minutes(args.quantidade, args.saida, client)
        elif args.listar:
            for f in list_material_facts(client, args.ano, args.empresa)[:20]:
                print(f"{f.delivery_date}  {f.company[:35]:<35}  {f.subject[:80]}")
            return 0
        else:
            paths = fetch_material_facts(args.empresa, args.ano, args.quantidade, args.saida, client)
    for path in paths:
        print(f"[ok] {path}")
    print("Próximo passo: uv run python -m backend.ingestion.cli")
    return 0


if __name__ == "__main__":
    sys.exit(main())
