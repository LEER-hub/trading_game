from __future__ import annotations

from pathlib import Path

from .agents import QLearningAgent
from .core import MarketConfig, MarketSimulator
from .scenarios import SyntheticScenarioGenerator


def train_self_play(
    output_dir: str | Path,
    *,
    episodes: int = 250,
    agent_count: int = 4,
    rounds: int = 100,
    seed: int = 7,
) -> list[QLearningAgent]:
    if episodes < 1 or agent_count < 2 or rounds < 1:
        raise ValueError("episodes and rounds must be positive; agent_count must be at least 2")
    agents = [QLearningAgent(f"agent-{number + 1}") for number in range(agent_count)]
    config = MarketConfig(rounds=rounds)
    for episode in range(episodes):
        events = SyntheticScenarioGenerator(seed + episode).standalone(rounds)
        MarketSimulator(config, seed + episode).run(agents, events, training=True)

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for agent in agents:
        agent.epsilon = 0.0
        agent.save(destination / f"{agent.agent_id}.json")
    return agents


def load_agents(model_dir: str | Path) -> list[QLearningAgent]:
    paths = sorted(Path(model_dir).glob("agent-*.json"))
    if not paths:
        raise FileNotFoundError(f"No agent-*.json models found in {model_dir}")
    return [QLearningAgent.load(path.stem, path) for path in paths]
