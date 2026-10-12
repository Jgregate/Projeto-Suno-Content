"""Reflection loop com LLM falso e avaliador roteirizado (sem rede)."""

from types import SimpleNamespace

from rich.console import Console

from backend.graph.build import build_graph
from backend.reflection.report import demo_path, reflection_stats
from backend.schemas import Audience, EvaluationReport, GraphState, MetricResult, NodeRun
from tests.fakes import FakeLLM
from tests.test_graph import make_doc

TARGET = "iniciante:texto"


class ScriptedEvaluator:
    """script[célula] = lista de tentativas; cada tentativa = [(métrica, score)], limiar 1 (min).
    Score 1 passa; abaixo de 1 a nota agregada da métrica é o próprio score. Células fora do script passam."""

    def __init__(self, script: dict[str, list[list[tuple[str, float]]]]):
        self.script = script
        self.calls: list[tuple[str, int]] = []

    def evaluate(self, out, source, extraction):
        self.calls.append((out.key, out.attempt))
        attempts = self.script.get(out.key, [[("ok", 1.0)]])
        spec = attempts[min(out.attempt, len(attempts)) - 1]
        metrics = [MetricResult(name=n, score=s, threshold=1.0, direction="min") for n, s in spec]
        report = EvaluationReport(
            audience=out.audience, format=out.format, attempt=out.attempt, metrics=metrics,
            feedback=f"corrija {[n for n, s in spec if s < 1]} (tentativa {out.attempt})",
        )
        return SimpleNamespace(report=report, runs=[NodeRun(node="evaluator:stub", cell=out.key, model="fake:judge")])


def refiner_calls(llm: FakeLLM) -> int:
    return sum(s.startswith("Você revisa um conteúdo") for s in llm.systems)


def run_loop(script, epsilon: float = 0.01, **kwargs) -> tuple[GraphState, FakeLLM, ScriptedEvaluator]:
    fast, evaluator = FakeLLM("fake:fast"), ScriptedEvaluator(script)
    graph = build_graph(fast, FakeLLM("fake:strong"), evaluator=evaluator, max_attempts=3, epsilon=epsilon)
    final = graph.invoke(GraphState(document=make_doc(), **kwargs))
    return GraphState.model_validate(final), fast, evaluator


def test_fails_then_passes_is_approved_after_1():
    state, fast, evaluator = run_loop({TARGET: [[("flesch_pt", 0.5)], [("flesch_pt", 1.0)]]})
    status = state.final_status[TARGET]
    assert status.status == "aprovado_apos_1" and status.attempts == 2 and status.delivered_attempt == 2
    assert all(s.status == "aprovado" for k, s in state.final_status.items() if k != TARGET)
    # só a reprovada volta: 1 refino e 9 + 1 avaliações
    assert refiner_calls(fast) == 1
    assert len(evaluator.calls) == 10 and (TARGET, 2) in evaluator.calls
    history = state.history[TARGET]
    assert [h.attempt for h in history] == [1, 2]
    assert history[1].injected_feedback == history[0].report.feedback != ""
    assert state.outputs[TARGET].attempt == 2


def test_always_failing_stops_at_3_and_delivers_best():
    state, fast, _ = run_loop({TARGET: [[("q", 0.3)], [("q", 0.6)], [("q", 0.9)]]})
    status = state.final_status[TARGET]
    assert status.status == "reprovado_final" and status.attempts == 3
    assert status.stop_reason == "max_tentativas" and status.delivered_attempt == 3
    assert refiner_calls(fast) == 2


def test_best_attempt_is_delivered_when_last_is_worse():
    # 0,3 -> 0,8 -> 0,4: a 3ª piora (também estagna) e a entregue é a 2ª
    state, _, _ = run_loop({TARGET: [[("q", 0.3)], [("q", 0.8)], [("q", 0.4)]]})
    status = state.final_status[TARGET]
    assert status.status == "reprovado_final" and status.delivered_attempt == 2
    assert state.outputs[TARGET].attempt == 2


def test_stagnation_stops_early():
    state, fast, _ = run_loop({TARGET: [[("q", 0.5)], [("q", 0.505)], [("q", 1.0)]]}, epsilon=0.01)
    status = state.final_status[TARGET]
    assert status.stop_reason == "estagnou" and status.attempts == 2
    assert refiner_calls(fast) == 1  # não pagou a 3ª tentativa


def test_regression_is_recorded():
    state, _, _ = run_loop({TARGET: [[("a", 1.0), ("b", 0.2)], [("a", 0.5), ("b", 1.0)], [("a", 1.0), ("b", 1.0)]]})
    second = state.history[TARGET][1]
    assert second.regressions == ["a"] and "regressao:a" in second.report.flags
    assert state.final_status[TARGET].regressions == ["a"]
    assert state.final_status[TARGET].status == "aprovado_apos_2"


def test_force_drift_uses_advanced_rules_on_first_attempt():
    fast, strong = FakeLLM("fake:fast"), FakeLLM("fake:strong")
    graph = build_graph(fast, strong, evaluator=ScriptedEvaluator({}), max_attempts=3)
    graph.invoke(GraphState(document=make_doc(), force_drift=Audience.BEGINNER))
    assert not any("Público: INICIANTE" in s for s in fast.systems)
    assert sum("Público: AVANÇADO" in s for s in fast.systems) == 2 * (1 + 3)  # adapter + 3 formatos, 2 níveis


def test_loop_stats():
    state, _, _ = run_loop({TARGET: [[("q", 0.5)], [("q", 1.0)]]})
    stats = reflection_stats(state)
    assert stats["cells"] == 9 and stats["refined_cells"] == 1
    assert stats["pct_approved_first"] == round(100 * 8 / 9, 1) and stats["pct_approved_final"] == 100.0
    assert stats["mean_attempts"] == round(10 / 9, 2) and stats["extra_llm_calls"] == 2  # 1 refino + 1 reavaliação


def test_force_drift_demo_file_and_terminal_view(tmp_path, monkeypatch):
    from backend import run as run_module
    from backend.reflection import show as show_reflection

    monkeypatch.setattr(run_module, "OUTPUTS_DIR", tmp_path)
    run_module.run(make_doc(), FakeLLM("fake:fast"), FakeLLM("fake:strong"), force_drift=Audience.BEGINNER)
    path = demo_path("ata-teste", tmp_path)
    assert path.exists()
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["drift_level"] == "iniciante" and set(payload["cells"]) == {"iniciante:texto", "iniciante:carrossel", "iniciante:roteiro"}
    console = Console(record=True, width=140)
    show_reflection.render(payload, show_reflection._pick_cell(payload["cells"], None), console)
    out = console.export_text()
    assert "Tentativas × métricas" in out and "flesch_pt" in out and "ANTES" in out
