"""API com TestClient sobre o grafo com LLM falso (sem rede)."""

import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend import run as run_module
from backend.api import main as api
from tests.fakes import FakeLLM

PDF_TEXT = "O Copom manteve a Selic em 15,00% a.a. A inflação segue em queda. Os juros reais seguem altos."


def make_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    # textos diferentes por página: bloco igual em todas as páginas é tratado como cabeçalho
    for text in (PDF_TEXT, "O comitê seguirá atento aos dados."):
        doc.new_page().insert_text((72, 100), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("OUTPUTS_DIR", "RAW_DIR", "PROCESSED_DIR"):
        (tmp_path / name).mkdir()
        monkeypatch.setattr(run_module, name, tmp_path / name)
    monkeypatch.setattr(api, "REPORTS_DIR", tmp_path / "OUTPUTS_DIR" / "reports")
    api.JOBS.clear()
    llms = {"fast": FakeLLM("fake:fast"), "strong": FakeLLM("fake:strong")}
    api.app.state.llm_factory = lambda: (llms["fast"], llms["strong"], llms["strong"])
    c = TestClient(api.app)
    c.llms = llms
    yield c
    api.app.state.llm_factory = api.default_llms


def upload(client) -> str:
    resp = client.post("/documents", files={"file": ("ata-copom-2026-09-16.pdf", make_pdf_bytes(), "application/pdf")})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_upload_run_results_flow(client):
    doc_id = upload(client)
    assert doc_id == "ata-copom-2026-09-16"
    docs = client.get("/documents").json()
    assert docs[0]["doc_type"] == "ata_copom" and docs[0]["date"] == "2026-09-16"

    created = client.post("/runs", json={"doc_id": doc_id}).json()
    assert created["cached"] is False
    status = client.get(f"/runs/{created['run_id']}").json()  # TestClient roda a background task antes de responder
    assert status["status"] == "completed", status["error"]
    assert status["progress"]["formatters"] == {"done": 9, "total": 9}
    assert status["progress"]["adapters"]["done"] == 3 and status["progress"]["evaluator"]["done"] >= 1

    results = client.get(f"/runs/{created['run_id']}/results").json()
    assert len(results["cells"]) == 9
    cell = results["cells"][0]
    assert {"audience", "format", "status", "content", "report", "history"} <= set(cell)
    assert cell["content"]["anchor_ids"] and cell["history"][0]["attempt"] == 1
    assert results["adapted"]["iniciante"]["claims"][0]["anchor_ids"] == ["A01"]

    anchors = client.get(f"/documents/{doc_id}/anchors").json()["anchors"]
    assert {a["id"] for a in anchors} == {"A01", "A02", "A03"}
    assert next(a for a in anchors if a["id"] == "A03")["valid"] is False

    summary = client.get("/reports/summary").json()
    assert summary["documents"] == [doc_id] and summary["reflection"][0]["cells"] == 9
    assert sum(map(sum, summary["confusion"]["pipeline"]["matrix"])) == 9


def test_demo_mode_serves_cache_without_llm(client):
    doc_id = upload(client)
    first = client.post("/runs", json={"doc_id": doc_id}).json()
    calls_after_first = len(client.llms["fast"].calls)

    def boom():
        raise AssertionError("modo demo não pode chamar LLM")

    api.app.state.llm_factory = boom
    again = client.post("/runs", json={"doc_id": doc_id}).json()
    assert again["cached"] is True and again["status"] == "completed"
    assert again["run_id"].startswith(f"{doc_id}__")
    assert client.get(f"/runs/{again['run_id']}/results").status_code == 200
    assert len(client.llms["fast"].calls) == calls_after_first
    assert first["run_id"] != again["run_id"]

    api.JOBS.clear()  # run_id persistente sobrevive a reinício da API
    assert client.get(f"/runs/{again['run_id']}").json()["status"] == "completed"


def test_errors(client):
    assert client.post("/runs", json={"doc_id": "nao-existe"}).status_code == 404
    assert client.get("/runs/xyz").status_code == 404
    assert client.post("/documents", files={"file": ("a.txt", b"oi", "text/plain")}).status_code == 415


def test_cors_for_vite(client):
    resp = client.options("/documents", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_openapi_export(tmp_path, monkeypatch):
    from backend.api import export_openapi

    monkeypatch.setattr(export_openapi, "OUT", tmp_path / "openapi.json")
    export_openapi.main()
    import json

    spec = json.loads((tmp_path / "openapi.json").read_text())
    assert {"/documents", "/runs", "/runs/{run_id}", "/runs/{run_id}/results", "/documents/{doc_id}/anchors", "/reports/summary"} <= set(spec["paths"])
    assert "RunResults" in spec["components"]["schemas"]


def test_reference_endpoints(client):
    doc_id = upload(client)
    run_id = client.post("/runs", json={"doc_id": doc_id}).json()["run_id"]

    glossary = client.get("/glossary").json()
    assert any(t["termo"] == "Selic" and t["nivel_minimo"] == "intermediario" for t in glossary)

    th = client.get("/thresholds").json()
    assert th["levels"]["iniciante"]["flesch_pt"] == {"min": 60.0, "max": None}
    assert th["common"]["claim_support"]["min"] == 0.95

    terms = client.get(f"/runs/{run_id}/cells/avancado/texto/terms").json()
    assert terms["attempt"] >= 1 and isinstance(terms["occurrences"], list)

    results = client.get(f"/runs/{run_id}/results").json()
    nodes = {n["node"] for n in results["node_costs"]}
    assert {"extractor", "adapter", "formatter", "evaluator:claims", "evaluator:judge"} <= nodes
    cell = results["cells"][0]
    assert cell["report"]["judge"] and cell["report"]["claims"][0]["verdict"] == "sustentada"

    summary = client.get("/reports/summary").json()
    assert len(summary["cells"]) == 9 and "flesch_pt" in summary["cells"][0]["metrics"]
    assert summary["node_costs"]


def test_terms_endpoint_marks_uncontextualized(client, monkeypatch):
    from backend.schemas import ArticleBody, Section
    from tests import fakes

    text = "O hiato do produto ficou positivo. A Selic, ou seja, o juro básico, caiu."
    original = fakes.FakeLLM.structured

    def structured(self, schema, system, user):
        res = original(self, schema, system, user)
        if schema is ArticleBody:
            res.parsed = ArticleBody(title="Juros", subtitle="Corte", sections=[Section(heading="O que houve", body=text, anchor_ids=["A01"])])
        return res

    monkeypatch.setattr(fakes.FakeLLM, "structured", structured)
    doc_id = upload(client)
    run_id = client.post("/runs", json={"doc_id": doc_id}).json()["run_id"]
    occ = {o["termo"]: o for o in client.get(f"/runs/{run_id}/cells/iniciante/texto/terms").json()["occurrences"]}
    assert occ["hiato do produto"]["contextualized"] is False and occ["hiato do produto"]["surface"] == "hiato do produto"
    assert occ["Selic"]["contextualized"] is True and occ["Selic"]["marker"] == "ou seja"


def test_documents_lists_merged_source_and_hides_its_parts(client):
    from backend.schemas import Page, SourceDocument

    for doc_id in ("fato-a", "fato-b", "ata-x"):
        doc = SourceDocument(id=doc_id, title=doc_id, text=PDF_TEXT, pages=[Page(number=1, text=PDF_TEXT)])
        (run_module.PROCESSED_DIR / f"{doc_id}.json").write_text(doc.model_dump_json(), encoding="utf-8")
    merged = run_module.OUTPUTS_DIR / "fato-a__fato-b"
    merged.mkdir()
    (merged / "20261016-000000-000000.json").write_text("{}", encoding="utf-8")

    ids = [d["id"] for d in client.get("/documents").json()]
    assert ids == ["fato-a__fato-b", "ata-x"]  # fonte unida com execução primeiro; partes escondidas
    assert run_module.load_document("fato-a__fato-b").pages[1].source_doc_id == "fato-b"


def test_summary_and_anchors_ignore_force_drift_runs(client):
    doc_id = upload(client)
    client.post("/runs", json={"doc_id": doc_id})
    client.post("/runs", json={"doc_id": doc_id, "force_drift": "iniciante"})  # demo gravada depois da normal
    runs = {
        p.stem: run_module.RunRecord.model_validate_json(p.read_text(encoding="utf-8")).force_drift
        for p in (run_module.OUTPUTS_DIR / doc_id).glob("*.json")
    }
    normal = next(stem for stem, drift in runs.items() if drift is None)
    assert len(runs) == 2
    assert client.get(f"/documents/{doc_id}/anchors").json()["run_id"] == f"{doc_id}__{normal}"
    assert len(client.get("/reports/summary").json()["reflection"]) == 1


def test_summary_uses_experiment_run_over_newer_generations(client, monkeypatch):
    doc_id = upload(client)
    client.post("/runs", json={"doc_id": doc_id})
    first = next((run_module.OUTPUTS_DIR / doc_id).glob("*.json"))
    exp = run_module.OUTPUTS_DIR / "experiment" / "2026-10-16"
    (exp / "runs").mkdir(parents=True)
    (exp / "csv").mkdir()
    (exp / "runs" / f"{doc_id}.json").write_bytes(first.read_bytes())
    (exp / "csv" / "metricas.csv").write_text("system,doc_id,audience,format,passed,flesch_pt,term_density,predicted_level\n", encoding="utf-8")
    client.post("/runs", json={"doc_id": doc_id, "force": True})  # geração ao vivo depois do experimento
    assert len(list((run_module.OUTPUTS_DIR / doc_id).glob("*.json"))) == 2

    def no_latest(*_):
        raise AssertionError("o resumo deveria usar a execução do experimento")

    monkeypatch.setattr(api, "_cached_path", no_latest)
    summary = client.get("/reports/summary").json()
    assert [r["doc_id"] for r in summary["reflection"]] == [doc_id]


def test_experiment_report_reads_csvs(client):
    csv = run_module.OUTPUTS_DIR / "experiment" / "2026-10-16" / "csv"
    csv.mkdir(parents=True)
    (csv.parent / "manifest.json").write_text('{"date": "2026-10-17"}', encoding="utf-8")
    (csv / "metricas.csv").write_text("system,doc_id,audience,format,passed,flesch_pt,term_density,predicted_level\n", encoding="utf-8")
    (csv / "variancia.csv").write_text("metric,media,desvio_medio_entre_repeticoes,desvio_max,tipo,repeticoes\nflesch_pt,44.8,0,0,deterministica,2\n",
                                       encoding="utf-8")
    (csv / "concordancia.csv").write_text("dimensao,n,concordancia,ic95_inf,ic95_sup,kappa_cohen\nerro factual,0,,,,\n", encoding="utf-8")
    e = client.get("/reports/experiment").json()
    assert e["date"] == "2026-10-17" and e["repeats"] == 2 and e["variance"][0]["desvio_medio"] == 0
    assert e["tradeoffs"] == [] and e["agreement"][0]["concordancia"] is None
