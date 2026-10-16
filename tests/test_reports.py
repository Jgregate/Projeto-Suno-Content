"""Ponta a ponta offline: pipeline + baseline (LLM falso) -> evaluate -> relatórios."""

import sys

import pandas as pd
import pytest

from backend import run as run_module
from backend.experiments import baseline as baseline_module
from backend.experiments import evaluate as evaluate_module
from backend.experiments.baseline import run_baseline
from backend.run import run
from tests.fakes import FakeLLM
from tests.test_graph import make_doc


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    for module in (run_module, baseline_module, evaluate_module):
        monkeypatch.setattr(module, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(evaluate_module, "REPORTS_DIR", tmp_path / "reports")
    return tmp_path


def test_baseline_has_no_extractor_and_nine_outputs(workspace):
    fast = FakeLLM("fake:fast")
    record, path, cached = run_baseline(make_doc(), fast)
    assert len(record.outputs) == 9 and not cached and path.parent.name == "baseline"
    assert set(fast.calls) == {"ArticleBody", "CarouselBody", "VideoScriptBody"}
    _, _, cached = run_baseline(make_doc(), fast)
    assert cached


def test_evaluate_writes_reports(workspace, monkeypatch):
    run(make_doc(), FakeLLM("fake:fast"), FakeLLM("fake:strong"))
    run_baseline(make_doc(), FakeLLM("fake:fast"))
    monkeypatch.setattr(sys, "argv", ["evaluate"])
    evaluate_module.main()

    reports = workspace / "reports"
    df = pd.read_csv(reports / "metricas.csv")
    assert len(df) == 18 and set(df.system) == {"pipeline", "baseline"}
    assert {"flesch_pt", "term_density", "numeric_grounding", "predicted_level", "flesch_textstat"} <= set(df.columns)
    # pipeline reaproveita os relatórios do grafo (com judge); baseline só determinístico
    assert df[df.system == "pipeline"].judge_tom.notna().all()
    assert df[df.system == "baseline"].get("judge_tom", pd.Series(dtype=float)).isna().all()

    matrix = pd.read_csv(reports / "matriz_confusao_pipeline.csv", index_col=0)
    assert matrix.values.sum() == 9
    assert (reports / "matriz_confusao_pipeline.png").exists()
    assert "## pipeline" in (reports / "reprovadas.md").read_text(encoding="utf-8")

    costs = pd.read_csv(reports / "custo_avaliador.csv")
    pipeline_cost = costs[costs.system == "pipeline"].iloc[0]
    assert pipeline_cost.llm_calls >= 18  # claims + judge do grafo (mais as reavaliações do loop)
