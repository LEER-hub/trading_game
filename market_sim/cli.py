from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agents import HeuristicAgent, HumanAgent
from .core import MarketConfig, MarketSimulator
from .forecasting import ProbabilityCalibrator, load_resolved_samples
from .providers import BBCNewsProvider, FTNewsProvider, KalshiProvider, PolymarketProvider
from .scenarios import SyntheticScenarioGenerator
from .training import load_agents, train_self_play


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research-only multi-agent market simulator")
    commands = parser.add_subparsers(dest="command", required=True)

    train = commands.add_parser("train", help="train tabular agents by synthetic self-play")
    train.add_argument("--episodes", type=int, default=250)
    train.add_argument("--agents", type=int, default=4)
    train.add_argument("--rounds", type=int, default=100)
    train.add_argument("--seed", type=int, default=7)
    train.add_argument("--output", default="models")

    simulate = commands.add_parser("simulate", help="run a trained or heuristic tournament")
    simulate.add_argument("--models", help="directory created by the train command")
    simulate.add_argument("--agents", type=int, default=4)
    simulate.add_argument("--rounds", type=int, default=50)
    simulate.add_argument("--seed", type=int, default=17)
    simulate.add_argument("--news", choices=("synthetic", "bbc", "ft"), default="synthetic")
    simulate.add_argument("--ft-query", default="markets")

    play = commands.add_parser("play", help="trade manually against AI opponents")
    play.add_argument("--models", help="optional directory of trained opponent models")
    play.add_argument("--opponents", type=int, default=3)
    play.add_argument("--rounds", type=int, default=20)
    play.add_argument("--seed", type=int, default=23)
    play.add_argument("--news", choices=("synthetic", "bbc", "ft"), default="synthetic")
    play.add_argument("--ft-query", default="markets")

    fetch = commands.add_parser("fetch-markets", help="read public prediction-market snapshots")
    fetch.add_argument("provider", choices=("kalshi", "polymarket"))
    fetch.add_argument("--limit", type=int, default=20)
    fetch.add_argument("--output", help="optional JSON output path")

    forecast = commands.add_parser("train-forecaster", help="calibrate probabilities using resolved snapshots")
    forecast.add_argument("--input", required=True, help="JSON rows with probability and resolved (0/1)")
    forecast.add_argument("--output", default="models/probability-calibrator.json")

    web = commands.add_parser("web", help="launch the live browser trading dashboard")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "train":
        agents = train_self_play(args.output, episodes=args.episodes, agent_count=args.agents, rounds=args.rounds, seed=args.seed)
        print(f"Saved {len(agents)} trained policies to {Path(args.output).resolve()}")
        return 0

    if args.command == "fetch-markets":
        provider = KalshiProvider() if args.provider == "kalshi" else PolymarketProvider()
        rows = provider.fetch(limit=args.limit)
        payload = [row.__dict__ for row in rows]
        rendered = json.dumps(payload, indent=2)
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
            print(f"Saved {len(rows)} read-only snapshots to {Path(args.output).resolve()}")
        else:
            print(rendered)
        return 0

    if args.command == "train-forecaster":
        samples = load_resolved_samples(args.input)
        model = ProbabilityCalibrator()
        model.fit(samples)
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        model.save(destination)
        print(f"Saved calibrator to {destination.resolve()} | training Brier score: {model.brier_score(samples):.4f}")
        return 0

    if args.command == "web":
        from .web_server import run_server

        run_server(args.host, args.port)
        return 0

    if args.command == "play":
        opponents = load_agents(args.models) if args.models else [
            HeuristicAgent(f"agent-{i + 1}", 0.75 + i * 0.2) for i in range(args.opponents)
        ]
        if args.models:
            opponents = opponents[: args.opponents]
        events = _build_events(args.news, args.rounds, args.seed, args.ft_query)
        print("You start with the same cash and position limits as every AI opponent.")
        print("Your news can arrive slightly earlier/later and with perception noise, just like theirs.")
        result = MarketSimulator(MarketConfig(rounds=args.rounds), args.seed).run([HumanAgent(), *opponents], events)
        print(f"\nGame over | Final price: {result.prices[-1]:.2f} | trades: {result.trades}")
        for rank, (name, pnl) in enumerate(result.leaderboard(), 1):
            marker = " <-- you" if name == "you" else ""
            print(f"{rank}. {name}: P&L {pnl:+.2f}{marker}")
        return 0

    agents = load_agents(args.models) if args.models else [HeuristicAgent(f"agent-{i + 1}", 0.75 + i * 0.2) for i in range(args.agents)]
    events = _build_events(args.news, args.rounds, args.seed, args.ft_query)
    result = MarketSimulator(MarketConfig(rounds=args.rounds), args.seed).run(agents, events)
    print(f"Final price: {result.prices[-1]:.2f} | trades: {result.trades}")
    for rank, (name, pnl) in enumerate(result.leaderboard(), 1):
        print(f"{rank}. {name}: P&L {pnl:+.2f}")
    return 0


def _build_events(news: str, rounds: int, seed: int, ft_query: str):
    generator = SyntheticScenarioGenerator(seed)
    if news == "bbc":
        events = generator.from_headlines(BBCNewsProvider().fetch(rounds), rounds)
    elif news == "ft":
        events = generator.from_headlines(FTNewsProvider().fetch(ft_query, rounds), rounds)
    else:
        events = generator.standalone(rounds)
    if len(events) < rounds:
        events.extend(generator.standalone(rounds - len(events)))
    return events
