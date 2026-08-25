from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import json
import math
import os
import random
import threading
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class AssetSpec:
    symbol: str
    name: str
    unit: str
    initial_price: float
    volatility: float
    decimals: int = 2
    provider_symbol: str | None = None


ASSETS = {
    item.symbol: item
    for item in (
        AssetSpec("GOLD", "Gold", "USD / troy oz", 2384.20, 0.00034, 2, "XAU/USD"),
        AssetSpec("SILVER", "Silver", "USD / troy oz", 30.18, 0.00055, 3, "XAG/USD"),
        AssetSpec("WTI", "WTI Crude Oil", "USD / barrel", 78.45, 0.00065, 2, "WTI/USD"),
        AssetSpec("BRENT", "Brent Crude Oil", "USD / barrel", 82.10, 0.00060, 2, "BRENT/USD"),
        AssetSpec("NATGAS", "Natural Gas", "USD / MMBtu", 2.74, 0.00120, 3, "XNG/USD"),
        AssetSpec("COPPER", "Copper", "USD / lb", 4.49, 0.00070, 3, "XCU/USD"),
    )
}


NEWS_TEMPLATES = (
    ("Supply outlook revised after new production estimates", 0.45),
    ("Inventory data surprises commodity desks", -0.35),
    ("Currency volatility shifts global demand expectations", 0.20),
    ("Transport disruption changes near-term supply forecasts", 0.55),
    ("Macro data points to softer industrial demand", -0.50),
)


@dataclass
class AssetState:
    spec: AssetSpec
    price: float
    previous_close: float
    anchor: float
    candles: deque = field(default_factory=lambda: deque(maxlen=360))
    ai_buys: int = 0
    ai_sells: int = 0
    active_agents: int = 0
    sentiment: float = 0.0
    headline: str = "AI market initializing"
    headline_at: float = 0.0


class TwelveDataPriceProvider:
    """Optional latest-price anchor. Availability depends on the user's plan."""

    URL = "https://api.twelvedata.com/price"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else os.getenv("TWELVE_DATA_API_KEY")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def fetch(self, provider_symbol: str) -> float:
        if not self.api_key:
            raise RuntimeError("TWELVE_DATA_API_KEY is not configured")
        url = f"{self.URL}?{urlencode({'symbol': provider_symbol, 'apikey': self.api_key})}"
        request = Request(url, headers={"User-Agent": "trading-game-research/1.0"})
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if "price" not in payload:
            raise RuntimeError(payload.get("message", f"No price returned for {provider_symbol}"))
        return float(payload["price"])


class LiveMarketEngine:
    """Aggregate cohort simulation representing millions of individual agents."""

    def __init__(
        self,
        *,
        seed: int = 41,
        population_per_asset: int = 1_000_000,
        tick_seconds: float = 1.0,
        provider: TwelveDataPriceProvider | None = None,
        provider_poll_seconds: float = 120.0,
    ):
        self.rng = random.Random(seed)
        self.population_per_asset = population_per_asset
        self.tick_seconds = tick_seconds
        self.provider = provider or TwelveDataPriceProvider()
        self.provider_poll_seconds = provider_poll_seconds
        self.states = {
            symbol: AssetState(spec, spec.initial_price, spec.initial_price, spec.initial_price)
            for symbol, spec in ASSETS.items()
        }
        self.cash = 100_000.0
        self.positions = {symbol: 0.0 for symbol in ASSETS}
        self.realized_pnl = 0.0
        self.version = 0
        self.started_at = time.time()
        self.last_provider_poll = 0.0
        self.provider_status = "connected" if self.provider.enabled else "simulation"
        self.provider_error: str | None = None
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._seed_history()

    def _seed_history(self) -> None:
        now = time.time()
        for state in self.states.values():
            price = state.price
            for offset in range(90, 0, -1):
                close = max(0.001, price * (1 + self.rng.gauss(0, state.spec.volatility)))
                high = max(price, close) * (1 + abs(self.rng.gauss(0, state.spec.volatility / 2)))
                low = min(price, close) * (1 - abs(self.rng.gauss(0, state.spec.volatility / 2)))
                state.candles.append(self._candle(now - offset * self.tick_seconds, price, high, low, close, 0))
                price = close
            state.price = price

    @staticmethod
    def _candle(timestamp: float, open_price: float, high: float, low: float, close: float, volume: int) -> dict[str, Any]:
        return {
            "time": round(timestamp * 1000),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="live-market-engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        next_tick = time.monotonic()
        while not self._stop.is_set():
            next_tick += self.tick_seconds
            self.tick_once()
            wait = max(0.0, next_tick - time.monotonic())
            self._stop.wait(wait)

    def tick_once(self) -> None:
        with self._lock:
            now = time.time()
            for state in self.states.values():
                self._advance_asset(state, now)
            self.version += 1
        if self.provider.enabled and time.time() - self.last_provider_poll >= self.provider_poll_seconds:
            self.last_provider_poll = time.time()
            threading.Thread(target=self._refresh_anchors, name="market-data-refresh", daemon=True).start()

    def _advance_asset(self, state: AssetState, now: float) -> None:
        recent = list(state.candles)[-8:]
        trend = (recent[-1]["close"] / recent[0]["close"] - 1) if len(recent) > 1 else 0.0
        anchor_gap = state.anchor / state.price - 1
        news_signal = state.sentiment * 0.00035
        if now - state.headline_at > 12 and self.rng.random() < 0.025:
            state.headline, state.sentiment = self.rng.choice(NEWS_TEMPLATES)
            state.headline = f"[SYNTHETIC] {state.headline}"
            state.headline_at = now
        elif now - state.headline_at > 8:
            state.sentiment *= 0.82

        # Four weighted cohorts: momentum, value, news, and noise traders.
        signal = 0.38 * math.tanh(trend * 900) + 0.25 * math.tanh(anchor_gap * 500)
        signal += 0.22 * state.sentiment + self.rng.gauss(0, 0.08)
        participation = min(0.018, max(0.002, 0.005 + abs(signal) * 0.004))
        active = int(self.population_per_asset * participation)
        buy_probability = min(0.92, max(0.08, 0.5 + signal * 0.30))
        expected_buys = active * buy_probability
        deviation = math.sqrt(active * buy_probability * (1 - buy_probability))
        buys = int(min(active, max(0, self.rng.gauss(expected_buys, deviation))))
        sells = active - buys
        imbalance = (buys - sells) / max(1, active)

        open_price = state.price
        external_pull = max(-0.002, min(0.002, anchor_gap * 0.08))
        market_move = external_pull + imbalance * state.spec.volatility * 0.8
        market_move += news_signal + self.rng.gauss(0, state.spec.volatility * 0.35)
        close = max(0.001, open_price * (1 + market_move))
        wick = abs(self.rng.gauss(0, state.spec.volatility * open_price * 0.35))
        state.price = close
        state.ai_buys, state.ai_sells, state.active_agents = buys, sells, active
        state.candles.append(self._candle(now, open_price, max(open_price, close) + wick, max(0.001, min(open_price, close) - wick), close, active))

    def _refresh_anchors(self) -> None:
        successes = 0
        errors = []
        for state in self.states.values():
            if not state.spec.provider_symbol:
                continue
            try:
                quote = self.provider.fetch(state.spec.provider_symbol)
                with self._lock:
                    state.anchor = quote
                successes += 1
            except Exception as exc:
                errors.append(f"{state.spec.symbol}: {exc}")
        with self._lock:
            self.provider_status = "connected" if successes else "provider-error"
            self.provider_error = "; ".join(errors)[:500] if errors else None

    def place_order(self, symbol: str, side: str, quantity: float) -> dict[str, Any]:
        if symbol not in self.states:
            raise ValueError("Unknown commodity")
        if side not in {"buy", "sell"}:
            raise ValueError("Side must be buy or sell")
        if not math.isfinite(quantity) or quantity <= 0 or quantity > 10_000:
            raise ValueError("Quantity must be between 0 and 10,000")
        with self._lock:
            price = self.states[symbol].price
            notional = price * quantity
            if side == "buy":
                if notional > self.cash:
                    raise ValueError("Insufficient simulated cash")
                self.cash -= notional
                self.positions[symbol] += quantity
            else:
                self.cash += notional
                self.positions[symbol] -= quantity
            self.version += 1
            return {"symbol": symbol, "side": side, "quantity": quantity, "price": price}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            assets = {}
            equity = self.cash
            for symbol, state in self.states.items():
                equity += self.positions[symbol] * state.price
                change = (state.price / state.previous_close - 1) * 100
                assets[symbol] = {
                    "symbol": symbol,
                    "name": state.spec.name,
                    "unit": state.spec.unit,
                    "price": state.price,
                    "change": change,
                    "decimals": state.spec.decimals,
                    "position": self.positions[symbol],
                    "activeAgents": state.active_agents,
                    "population": self.population_per_asset,
                    "aiBuys": state.ai_buys,
                    "aiSells": state.ai_sells,
                    "sentiment": state.sentiment,
                    "headline": state.headline,
                    "candles": list(state.candles),
                }
            return {
                "version": self.version,
                "serverTime": round(time.time() * 1000),
                "source": self.provider_status,
                "sourceError": self.provider_error,
                "population": self.population_per_asset * len(self.states),
                "cash": self.cash,
                "equity": equity,
                "pnl": equity - 100_000.0,
                "assets": assets,
            }
