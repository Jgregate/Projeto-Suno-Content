"""Classificador de nível a partir das métricas determinísticas.

Usa só métricas que não dependem do nível-alvo (Flesch e densidade; a % de
contextualização depende do nível pedido, então fica de fora).

Regra:
1. Níveis cujas faixas o texto atende (distância 0 em todas as métricas).
2. Se exatamente um: é ele.
3. Se nenhum: menor distância normalizada às faixas (soma das métricas).
4. Se empate (vários atendem): vence o nível com mais faixas definidas atendidas
   (restrição mais específica = evidência mais forte; o Avançado não tem faixa de Flesch),
   e depois a menor distância normalizada ao centro das faixas.
"""

from backend.evaluator.thresholds import Thresholds, load_thresholds
from backend.schemas import Audience


def predict_level(metrics: dict[str, float], thresholds: Thresholds | None = None) -> Audience:
    thresholds = thresholds or load_thresholds()
    names: list[str] = thresholds.classifier["metrics"]
    scale: dict[str, float] = thresholds.classifier["scale"]

    def edge_distance(level: Audience) -> float:
        return sum(thresholds.level_bound(level, m).distance(metrics[m], scale[m]) for m in names)

    def center_distance(level: Audience) -> float:
        total = 0.0
        for m in names:
            center = thresholds.level_bound(level, m).center()
            if center is not None:
                total += abs(metrics[m] - center) / scale[m]
        return total

    distances = {level: edge_distance(level) for level in Audience}
    inside = [lvl for lvl, d in distances.items() if d == 0]
    if len(inside) == 1:
        return inside[0]
    if not inside:
        return min(distances, key=lambda lvl: (distances[lvl], list(Audience).index(lvl)))
    def bounded(level: Audience) -> int:
        return sum(thresholds.level_bound(level, m).center() is not None for m in names)

    return min(inside, key=lambda lvl: (-bounded(lvl), center_distance(lvl), list(Audience).index(lvl)))
