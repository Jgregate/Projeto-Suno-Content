"""Leitura de thresholds.yaml e conversão de limiares em MetricResult."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from backend.config import THRESHOLDS_PATH
from backend.schemas import Audience, Format, MetricResult


@dataclass(frozen=True)
class Bound:
    min: float | None = None
    max: float | None = None

    def metric(self, name: str, score: float, details: str = "") -> MetricResult:
        if self.min is not None and self.max is not None:
            return MetricResult(name=name, score=score, threshold=self.min, threshold_max=self.max, direction="range", details=details)
        if self.min is not None:
            return MetricResult(name=name, score=score, threshold=self.min, direction="min", details=details)
        if self.max is not None:
            return MetricResult(name=name, score=score, threshold=self.max, direction="max", details=details)
        return MetricResult(name=name, score=score, direction="info", details=details)

    def distance(self, value: float, scale: float) -> float:
        """0 dentro da faixa; senão, distância à borda mais próxima / escala."""
        if self.min is not None and value < self.min:
            return (self.min - value) / scale
        if self.max is not None and value > self.max:
            return (value - self.max) / scale
        return 0.0

    def center(self) -> float | None:
        if self.min is not None and self.max is not None:
            return (self.min + self.max) / 2
        return self.min if self.min is not None else self.max


@dataclass(frozen=True)
class Thresholds:
    raw: dict

    def for_cell(self, audience: Audience, fmt: Format) -> dict[str, Bound]:
        merged = {**self.raw["levels"][audience.value]}
        merged.update((self.raw.get("formats", {}).get(fmt.value) or {}).get(audience.value, {}))
        merged.update(self.raw["common"])
        return {name: Bound(cfg.get("min"), cfg.get("max")) for name, cfg in merged.items()}

    def level_bound(self, audience: Audience, metric: str) -> Bound:
        cfg = self.raw["levels"][audience.value].get(metric) or {}
        return Bound(cfg.get("min"), cfg.get("max"))

    @property
    def factuality(self) -> dict:
        return self.raw["factuality"]

    @property
    def classifier(self) -> dict:
        return self.raw["classifier"]


@lru_cache
def load_thresholds(path: Path = THRESHOLDS_PATH) -> Thresholds:
    return Thresholds(yaml.safe_load(path.read_text(encoding="utf-8")))
