# Multi-agent trading game

This project is a research-only market simulator. Agents begin with identical cash, position limits, execution access, and public event streams. Real-world differences are simulated with small independent observation noise and 0–2 round news delays.

It does **not** place trades, connect to brokerage accounts, or promise investment performance.

## Live web dashboard

Launch the browser-based commodity exchange:

```powershell
python trading_game.py web --host 127.0.0.1 --port 8000
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). The dashboard streams Gold, Silver, WTI, Brent, Natural Gas, and Copper prices; supports candlestick and line charts; displays aggregate AI order flow; and lets you place simulated buy/sell orders.

The default engine represents one million agents per commodity using weighted behavioral cohorts. It deliberately does not allocate six million Python objects. Cohorts model momentum, value, news, and noise behavior and produce statistically scaled order counts each tick.

### Optional external commodity-price anchors

The website runs without any API key in clearly labeled simulation mode. To enable Twelve Data price anchors:

```powershell
$env:TWELVE_DATA_API_KEY = "your-key"
python trading_game.py web
```

Provider availability, instrument symbols, delay, exchange coverage, redistribution rights, and rate limits depend on your Twelve Data plan. External observations anchor the simulation; the displayed tick-by-tick order book and fills remain fictional. Never label the result as an executable or exchange-sourced price.

## Quick start

Python 3.10+ is sufficient; there are no third-party packages.

```powershell
python trading_game.py train --episodes 250 --agents 4 --rounds 100 --output models
python trading_game.py simulate --models models --rounds 50
python -m unittest discover -s tests -v
```

Play manually against three AI opponents:

```powershell
python trading_game.py play --models models --opponents 3 --rounds 20
```

Each round, enter `b` to buy one unit, `s` to sell one unit, or `h` to hold. After the last round, all portfolios are marked to the final price and ranked by profit and loss. Omit `--models models` to play against built-in heuristic opponents.

Use BBC business headlines as topic seeds for clearly labeled fictional scenarios:

```powershell
python trading_game.py simulate --models models --news bbc
```

The source headline is never altered and presented as genuine. Instead, it selects a generic theme for a separate `[SYNTHETIC/...]` event. The event keeps source attribution and URL for provenance. Check the BBC feed terms for your use, especially for commercial use.

FT access requires a licensed Content API key:

```powershell
$env:FT_API_KEY = "your-key"
python trading_game.py simulate --models models --news ft --ft-query "markets"
```

## Prediction-market data

Kalshi and Polymarket adapters only read public market snapshots; they never submit orders:

```powershell
python trading_game.py fetch-markets kalshi --limit 50 --output data/kalshi.json
python trading_game.py fetch-markets polymarket --limit 50 --output data/polymarket.json
```

A current probability is not a labeled training example. To train the included calibration model, retain snapshots until resolution and add a `resolved` field (`0` or `1`) to each row. Use chronological train/validation splits in serious experiments to prevent look-ahead leakage.

```json
[
  {"probability": 0.31, "resolved": 0},
  {"probability": 0.74, "resolved": 1}
]
```

```powershell
python trading_game.py train-forecaster --input data/resolved.json --output models/probability-calibrator.json
```

The command reports an in-sample Brier score. Evaluate a held-out, chronologically later set before drawing conclusions. Exchange probabilities can be useful features, but training only on their consensus generally learns to imitate/calibrate the exchange rather than discover an independent edge.

## Architecture

- `market_sim/core.py`: exchange, portfolios, equal starting resources, market impact, and per-agent information discrepancies.
- `market_sim/agents.py`: heuristic and persisted tabular self-play policies.
- `market_sim/scenarios.py`: labeled fictional event generation.
- `market_sim/providers.py`: opt-in BBC RSS, licensed FT, public Kalshi, and public Polymarket readers.
- `market_sim/forecasting.py`: probability calibration from resolved market samples.
- `market_sim/training.py`: reproducible self-play training and model persistence.

## Important research limitations

This is a compact baseline, not a production-grade market model. It omits fees, queue priority, partial fills, latency topology, corporate actions, borrow costs, and realistic order-book replay. News-impact labels are synthetic rather than inferred from copyrighted article bodies. For trustworthy forecasting work, archive legally permitted timestamps and outcomes, use walk-forward validation, measure Brier/log loss and calibration, and compare against the raw market probability as the baseline.
