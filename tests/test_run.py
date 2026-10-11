import pytest

from backend import run as run_module
from backend.run import merge_documents, run
from backend.schemas import Page, SourceDocument
from tests.fakes import FakeLLM
from tests.test_graph import make_doc


@pytest.fixture
def outputs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(run_module, "OUTPUTS_DIR", tmp_path)
    return tmp_path


def test_run_saves_and_reuses_cache(outputs_dir):
    fast, strong = FakeLLM("fake:fast"), FakeLLM("fake:strong")
    record, path, cached = run(make_doc(), fast, strong)
    assert not cached and path.parent == outputs_dir / "ata-teste"
    # 13 de geração + 18 de avaliação na 1ª passada; o loop soma refinos e reavaliações
    assert len(record.state.outputs) == 9 and record.totals.llm_calls >= 13 + 18
    assert record.generation.llm_calls >= 13 and record.evaluation.llm_calls >= 18
    assert record.totals.llm_calls == record.generation.llm_calls + record.evaluation.llm_calls
    assert record.totals.input_tokens > 0 and record.evaluation.wall_ms >= 0

    calls = len(fast.calls)
    _, path2, cached2 = run(make_doc(), fast, strong)
    assert cached2 and path2 == path and len(fast.calls) == calls  # nenhuma chamada nova


def test_force_and_model_change_skip_cache(outputs_dir):
    run(make_doc(), FakeLLM("fake:fast"), FakeLLM("fake:strong"))
    _, _, cached = run(make_doc(), FakeLLM("fake:fast"), FakeLLM("fake:strong"), force=True)
    assert not cached
    _, _, cached = run(make_doc(), FakeLLM("fake:outro"), FakeLLM("fake:strong"))
    assert not cached


def test_merge_documents_renumbers_pages():
    a = SourceDocument(id="fato-a", title="A", text="x", pages=[Page(number=1, text="x"), Page(number=2, text="y")])
    b = SourceDocument(id="fato-b", title="B", text="z", pages=[Page(number=1, text="z")])
    merged = merge_documents([a, b])
    assert merged.id == "fato-a__fato-b"
    assert [(p.number, p.source_doc_id) for p in merged.pages] == [(1, "fato-a"), (2, "fato-a"), (3, "fato-b")]


def test_get_llm_fails_fast_without_config(monkeypatch):
    from backend.config import settings
    from backend.llm import get_llm

    monkeypatch.setattr(settings, "llm_fast_model", "provider:model-name")
    with pytest.raises(RuntimeError, match="LLM_FAST_MODEL"):
        get_llm("fast")


def test_langchain_llm_retries_once_on_parse_error():
    from types import SimpleNamespace

    from backend.llm import LangChainLLM
    from backend.schemas import KeyNumber

    outputs = [
        {"raw": SimpleNamespace(usage_metadata={"input_tokens": 10, "output_tokens": 5}), "parsed": None, "parsing_error": "x"},
        {"raw": SimpleNamespace(usage_metadata={"input_tokens": 12, "output_tokens": 6}), "parsed": KeyNumber(label="Selic", value="15%")},
    ]
    seen: list[int] = []

    class Runnable:
        def invoke(self, messages):
            seen.append(len(messages))
            return outputs.pop(0)

    llm = object.__new__(LangChainLLM)
    llm.model_id = "stub:model"
    llm._model = SimpleNamespace(with_structured_output=lambda schema, include_raw: Runnable())
    result = llm.structured(KeyNumber, "sys", "user")
    assert result.parsed.label == "Selic"
    assert (result.input_tokens, result.output_tokens) == (22, 11)
    assert seen == [2, 3]  # 2ª chamada leva o erro de volta ao modelo
