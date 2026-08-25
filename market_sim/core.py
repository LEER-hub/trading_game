from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Protocol, Sequence


@dataclass(frozen=True)
class NewsEvent:
    headline: str
    impact: float
    source: str = "synthetic"
    synthetic: bool = True
    url: str | None = None


@dataclass(frozen=True)
class Observation:
    step: int
    price: float
    perceived_news_impact: float
    position: int
    cash: float
    news_headline: str | None = None


@dataclass(frozen=True)
class Order:
    agent_id: str
    side: str
    quantity: int
    limit_price: float


@dataclass
class Portfolio:
    cash: float
    position: int = 0

    def equity(self, mark: float) -> float:
        return self.cash + self.position * mark


class TradingAgent(Protocol):
    agent_id: str

    def act(self, observation: Observation, rng: random.Random) -> int:
        """Return -1 (sell), 0 (hold), or 1 (buy)."""


@dataclass(frozen=True)
class MarketConfig:
    initial_price: float = 100.0
    initial_cash: float = 10_000.0
    rounds: int = 100
    max_position: int = 20
    spread: float = 0.10
    liquidity: float = 25.0
    volatility: float = 0.20
    information_noise: float = 0.12
    max_news_delay: int = 2


@dataclass
class SimulationResult:
    prices: list[float]
    portfolios: dict[str, Portfolio]
    initial_cash: float
    trades: int
    news_log: list[dict] = field(default_factory=list)

    def leaderboard(self) -> list[tuple[str, float]]:
        final = self.prices[-1]
        return sorted(
            ((name, book.equity(final) - self.initial_cash) for name, book in self.portfolios.items()),
            key=lambda row: row[1],
            reverse=True,
        )


class MarketSimulator:
    """A reproducible toy exchange for research and education, not execution."""

    def __init__(self, config: MarketConfig | None = None, seed: int = 7):
        self.config = config or MarketConfig()
        self.seed = seed

    def run(
        self,
        agents: Sequence[TradingAgent],
        events: Sequence[NewsEvent] = (),
        training: bool = False,
    ) -> SimulationResult:
        if len({agent.agent_id for agent in agents}) != len(agents):
            raise ValueError("agent_id values must be unique")
        rng = random.Random(self.seed)
        cfg = self.config
        price = cfg.initial_price
        prices = [price]
        books = {a.agent_id: Portfolio(cfg.initial_cash) for a in agents}
        schedules = self._information_schedules(agents, events, rng)
        news_log: list[dict] = []
        trades = 0

        for step in range(cfg.rounds):
            public_event = events[step] if step < len(events) else None
            fundamental_impact = public_event.impact if public_event else 0.0
            if public_event:
                news_log.append({
                    "step": step,
                    "headline": public_event.headline,
                    "source": public_event.source,
                    "synthetic": public_event.synthetic,
                    "impact": public_event.impact,
                })

            old_equity = {name: book.equity(price) for name, book in books.items()}
            orders: list[Order] = []
            for agent in agents:
                book = books[agent.agent_id]
                perceived, perceived_headline = schedules[agent.agent_id].get(step, (0.0, None))
                observed_price = max(0.01, price + rng.gauss(0, cfg.information_noise))
                obs = Observation(step, observed_price, perceived, book.position, book.cash, perceived_headline)
                action = int(agent.act(obs, rng))
                if action > 0 and book.position < cfg.max_position:
                    orders.append(Order(agent.agent_id, "buy", 1, price + cfg.spread / 2))
                elif action < 0 and book.position > -cfg.max_position:
                    orders.append(Order(agent.agent_id, "sell", 1, price - cfg.spread / 2))

            buys = [o for o in orders if o.side == "buy"]
            sells = [o for o in orders if o.side == "sell"]
            # A neutral liquidity pool fills eligible orders. This lets self-play
            # learn even when every agent initially chooses the same action.
            for order in orders:
                book = books[order.agent_id]
                if order.side == "buy" and book.cash >= order.limit_price:
                    book.cash -= order.limit_price
                    book.position += 1
                    trades += 1
                elif order.side == "sell":
                    book.cash += order.limit_price
                    book.position -= 1
                    trades += 1

            imbalance = len(buys) - len(sells)
            price = max(
                0.01,
                price + fundamental_impact + imbalance / cfg.liquidity + rng.gauss(0, cfg.volatility),
            )
            prices.append(price)

            if training:
                for agent in agents:
                    learn = getattr(agent, "learn", None)
                    if learn:
                        reward = books[agent.agent_id].equity(price) - old_equity[agent.agent_id]
                        learn(reward, price)

        return SimulationResult(prices, books, cfg.initial_cash, trades, news_log)

    def _information_schedules(self, agents, events, rng):
        schedules: dict[str, dict[int, float]] = {a.agent_id: {} for a in agents}
        for event_step, event in enumerate(events[: self.config.rounds]):
            for agent in agents:
                delay = rng.randint(0, self.config.max_news_delay)
                noise = rng.gauss(0, self.config.information_noise)
                arrival = min(self.config.rounds - 1, event_step + delay)
                schedules[agent.agent_id][arrival] = (event.impact + noise, event.headline)
        return schedules
