from __future__ import annotations

import random
from typing import Sequence

from .core import NewsEvent
from .providers import NewsItem


THEMES = {
    "rates": (("rate", "inflation", "central bank"), "A surprise policy-rate signal changes financing expectations"),
    "growth": (("growth", "gdp", "jobs", "economy"), "An unexpected growth indicator changes the economic outlook"),
    "company": (("profit", "earnings", "company", "shares"), "A large listed company issues an unexpected trading update"),
    "energy": (("oil", "gas", "energy"), "An unexpected energy-supply disruption reaches the market"),
}


class SyntheticScenarioGenerator:
    """Creates labeled fictional events; it never presents altered news as real."""

    def __init__(self, seed: int = 7):
        self.rng = random.Random(seed)

    def from_headlines(self, items: Sequence[NewsItem], count: int = 20) -> list[NewsEvent]:
        events = []
        for item in items[:count]:
            key, template = self._theme(item.headline)
            sign = self.rng.choice((-1.0, 1.0))
            magnitude = self.rng.uniform(0.25, 1.75)
            events.append(NewsEvent(
                headline=f"[SYNTHETIC/{key.upper()}] {template}",
                impact=round(sign * magnitude, 3),
                source=f"synthetic scenario; theme seed: {item.source}",
                synthetic=True,
                url=item.url,
            ))
        return events

    def standalone(self, count: int = 20) -> list[NewsEvent]:
        placeholders = [NewsItem(template, "built-in") for _, template in THEMES.values()]
        return self.from_headlines([self.rng.choice(placeholders) for _ in range(count)], count)

    @staticmethod
    def _theme(headline: str) -> tuple[str, str]:
        lowered = headline.lower()
        for key, (terms, template) in THEMES.items():
            if any(term in lowered for term in terms):
                return key, template
        return "macro", "An unanticipated macroeconomic announcement reaches the market"
