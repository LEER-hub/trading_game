from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Iterable


def _logit(probability: float) -> float:
    p = min(0.999, max(0.001, probability))
    return math.log(p / (1 - p))


@dataclass
class ProbabilityCalibrator:
    """Small logistic calibration model for resolved prediction-market samples."""

    weight: float = 1.0
    bias: float = 0.0

    def predict(self, market_probability: float) -> float:
        score = self.weight * _logit(market_probability) + self.bias
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, score))))

    def fit(self, samples: Iterable[tuple[float, int]], epochs: int = 1500, learning_rate: float = 0.02) -> None:
        rows = list(samples)
        if len(rows) < 10:
            raise ValueError("At least 10 resolved samples are required")
        for probability, resolved in rows:
            if not 0 <= probability <= 1 or resolved not in (0, 1):
                raise ValueError("Samples must contain probability in [0,1] and resolved as 0 or 1")
        for _ in range(epochs):
            dw = db = 0.0
            for probability, resolved in rows:
                error = self.predict(probability) - resolved
                dw += error * _logit(probability)
                db += error
            scale = learning_rate / len(rows)
            self.weight -= scale * dw
            self.bias -= scale * db

    def brier_score(self, samples: Iterable[tuple[float, int]]) -> float:
        rows = list(samples)
        if not rows:
            raise ValueError("No samples supplied")
        return sum((self.predict(p) - y) ** 2 for p, y in rows) / len(rows)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.__dict__, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "ProbabilityCalibrator":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


def load_resolved_samples(path: str | Path) -> list[tuple[float, int]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(float(row["probability"]), int(row["resolved"])) for row in payload]
