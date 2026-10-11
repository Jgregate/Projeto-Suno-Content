"""Montagem do StateGraph.

extractor -> adapter_<nível> (x3, paralelo) -> fmt_<nível>_<formato> (x9, paralelo)
          -> evaluator (células pendentes em paralelo)
          -> [approve] END
          -> [retry]   refiner (só as reprovadas, em paralelo) -> evaluator -> ...
Máximo de MAX_RETRIES tentativas por célula; parada antecipada se a nota agregada estagnar.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.evaluator.glossary import Glossary, TermMatcher, load_glossary
from backend.evaluator.hybrid import HybridEvaluator
from backend.llm import LLMClient
from backend.nodes.adapter import make_adapter
from backend.nodes.evaluator import Evaluates, make_evaluator, route_after_eval
from backend.nodes.extractor import make_extractor
from backend.nodes.formatter import make_formatter
from backend.nodes.refiner import make_refiner
from backend.schemas import Audience, Format, GraphState


def build_graph(
    fast: LLMClient,
    strong: LLMClient,
    judge: LLMClient | None = None,
    glossary: Glossary | None = None,
    use_llm_eval: bool = True,
    evaluator: Evaluates | None = None,
    refiner_llm: LLMClient | None = None,
    max_attempts: int | None = None,
    epsilon: float | None = None,
    claims: LLMClient | None = None,
) -> CompiledStateGraph:
    """`judge` avalia (judge e, sem `claims`, também a fidelidade por afirmações); padrão = `strong`. `use_llm_eval=False` deixa só as métricas determinísticas.
    `evaluator` permite injetar um avaliador (testes). O refiner usa `refiner_llm` ou o `fast`.
    Formatters e refiner caem para o `strong` quando o modelo barato não entrega o schema."""
    glossary = glossary or load_glossary()
    matcher = TermMatcher(glossary)
    judge_llm = (judge or strong) if use_llm_eval else None
    claims_llm = (claims or judge_llm) if use_llm_eval else None
    hybrid = evaluator or HybridEvaluator(matcher, claims_llm=claims_llm, judge_llm=judge_llm)

    graph = StateGraph(GraphState)
    graph.add_node("extractor", make_extractor(strong, matcher))
    graph.add_edge(START, "extractor")

    formatter_nodes: list[str] = []
    for audience in Audience:
        adapter = f"adapter_{audience.value}"
        graph.add_node(adapter, make_adapter(audience, fast, glossary))
        graph.add_edge("extractor", adapter)
        for fmt in Format:
            name = f"fmt_{audience.value}_{fmt.value}"
            graph.add_node(name, make_formatter(audience, fmt, fast, fallback=strong))
            graph.add_edge(adapter, name)
            formatter_nodes.append(name)

    graph.add_node("evaluator", make_evaluator(hybrid, max_attempts=max_attempts, epsilon=epsilon))
    graph.add_edge(formatter_nodes, "evaluator")  # join: espera as 9 células
    graph.add_node("refiner", make_refiner(refiner_llm or fast, glossary, fallback=strong))
    graph.add_conditional_edges("evaluator", route_after_eval, {"approve": END, "retry": "refiner"})
    graph.add_edge("refiner", "evaluator")
    return graph.compile()
