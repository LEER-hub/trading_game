from __future__ import annotations

from dataclasses import dataclass, field
import json
import random
from pathlib import Path

from .core import Observation


@dataclass
class HeuristicAgent:
    agent_id: str
    risk: float = 1.0

    def act(self, observation: Observation, rng: random.Random) -> int:
        score = observation.perceived_news_impact * self.risk - observation.position * 0.025
        score += rng.gauss(0, 0.12)
        return 1 if score > 0.10 else -1 if score < -0.10 else 0


@dataclass
class HumanAgent:
    agent_id: str = "you"

    def act(self, observation: Observation, rng: random.Random) -> int:
        print(f"\n--- Round {observation.step + 1} ---")
        print(f"Observed price: {observation.price:.2f}")
        if observation.news_headline:
            print(f"News received: {observation.news_headline}")
            print(f"Your perceived impact: {observation.perceived_news_impact:+.2f}")
        else:
            print("News received: none this round")
        print(f"Cash: {observation.cash:.2f} | Position: {observation.position}")
        while True:
            try:
                choice = input("Action [b]uy, [s]ell, [h]old: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("Holding.")
                return 0
            if choice in {"b", "buy"}:
                return 1
            if choice in {"s", "sell"}:
                return -1
            if choice in {"h", "hold", "", "pass"}:
                return 0
            print("Please enter b, s, or h.")


@dataclass
class QLearningAgent:
    agent_id: str
    alpha: float = 0.12
    epsilon: float = 0.10
    q: dict[str, list[float]] = field(default_factory=dict)
    _last_state: str | None = field(default=None, repr=False)
    _last_action: int | None = field(default=None, repr=False)

    @staticmethod
    def _state(observation: Observation) -> str:
        news = -1 if observation.perceived_news_impact < -0.15 else 1 if observation.perceived_news_impact > 0.15 else 0
        inventory = -1 if observation.position < -2 else 1 if observation.position > 2 else 0
        return f"{news}:{inventory}"

    def act(self, observation: Observation, rng: random.Random) -> int:
        state = self._state(observation)
        values = self.q.setdefault(state, [0.0, 0.0, 0.0])
        index = rng.randrange(3) if rng.random() < self.epsilon else max(range(3), key=values.__getitem__)
        self._last_state, self._last_action = state, index
        return (-1, 0, 1)[index]

    def learn(self, reward: float, _next_price: float) -> None:
        if self._last_state is None or self._last_action is None:
            return
        values = self.q[self._last_state]
        # This compact baseline uses a one-step return (gamma=0). Adding price
        # history to the state is the natural next step for multi-step RL.
        values[self._last_action] += self.alpha * (reward - values[self._last_action])

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({"q": self.q}, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, agent_id: str, path: str | Path) -> "QLearningAgent":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(agent_id=agent_id, epsilon=0.0, q=payload["q"])
