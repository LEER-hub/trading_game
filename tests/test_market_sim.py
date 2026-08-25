import json
from pathlib import Path
import tempfile
import unittest

from market_sim.agents import HeuristicAgent, HumanAgent, QLearningAgent
from market_sim.core import MarketConfig, MarketSimulator, NewsEvent
from market_sim.forecasting import ProbabilityCalibrator
from market_sim.live_engine import LiveMarketEngine, TwelveDataPriceProvider
from market_sim.providers import NewsItem
from market_sim.scenarios import SyntheticScenarioGenerator
from market_sim.training import load_agents, train_self_play


class MarketTests(unittest.TestCase):
    def test_live_engine_aggregates_million_agent_cohorts(self):
        engine = LiveMarketEngine(seed=2, population_per_asset=1_000_000, provider=TwelveDataPriceProvider(api_key=""))
        before = engine.snapshot()
        engine.tick_once()
        after = engine.snapshot()
        self.assertEqual(after["population"], 6_000_000)
        self.assertGreater(after["version"], before["version"])
        for asset in after["assets"].values():
            self.assertEqual(asset["aiBuys"] + asset["aiSells"], asset["activeAgents"])
            self.assertGreater(len(asset["candles"]), 90)

    def test_live_engine_executes_simulated_human_order(self):
        engine = LiveMarketEngine(seed=3, provider=TwelveDataPriceProvider(api_key=""))
        price = engine.snapshot()["assets"]["GOLD"]["price"]
        trade = engine.place_order("GOLD", "buy", 2)
        snapshot = engine.snapshot()
        self.assertEqual(trade["side"], "buy")
        self.assertEqual(snapshot["assets"]["GOLD"]["position"], 2)
        self.assertAlmostEqual(snapshot["cash"], 100_000 - price * 2)

    def test_human_agent_accepts_short_action(self):
        from unittest.mock import patch
        from market_sim.core import Observation

        observation = Observation(0, 100.0, 0.2, 0, 10_000.0, "[SYNTHETIC] Test")
        with patch("builtins.input", return_value="b"):
            self.assertEqual(HumanAgent().act(observation, __import__("random").Random()), 1)

    def test_agents_start_equal_and_result_is_reproducible(self):
        agents1 = [HeuristicAgent("a"), HeuristicAgent("b")]
        agents2 = [HeuristicAgent("a"), HeuristicAgent("b")]
        events = [NewsEvent("[SYNTHETIC] test", 1.0)] * 5
        config = MarketConfig(rounds=5, initial_cash=500.0)
        first = MarketSimulator(config, seed=3).run(agents1, events)
        second = MarketSimulator(config, seed=3).run(agents2, events)
        self.assertEqual(first.prices, second.prices)
        self.assertEqual(first.initial_cash, 500.0)
        self.assertEqual(set(first.portfolios), {"a", "b"})

    def test_scenarios_are_unambiguously_synthetic(self):
        item = NewsItem("Central bank discusses rates", "BBC News", "https://example.test")
        event = SyntheticScenarioGenerator(1).from_headlines([item])[0]
        self.assertTrue(event.synthetic)
        self.assertTrue(event.headline.startswith("[SYNTHETIC/"))
        self.assertEqual(event.url, item.url)

    def test_training_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            train_self_play(folder, episodes=3, agent_count=2, rounds=5)
            loaded = load_agents(folder)
            self.assertEqual(len(loaded), 2)
            self.assertTrue(all(agent.epsilon == 0 for agent in loaded))

    def test_calibrator_learns_and_serializes(self):
        samples = [(0.05 + i * 0.045, int(i >= 10)) for i in range(20)]
        model = ProbabilityCalibrator()
        before = model.brier_score(samples)
        model.fit(samples, epochs=300)
        self.assertLess(model.brier_score(samples), before)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.json"
            model.save(path)
            self.assertAlmostEqual(model.predict(0.7), ProbabilityCalibrator.load(path).predict(0.7))


if __name__ == "__main__":
    unittest.main()
