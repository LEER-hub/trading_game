from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree


USER_AGENT = "trading-game-research/1.0"


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class NewsItem:
    headline: str
    source: str
    url: str | None = None
    published_at: str | None = None


@dataclass(frozen=True)
class PredictionMarket:
    market_id: str
    question: str
    probability: float | None
    volume: float | None
    source: str


def _request_json(url: str, *, headers: dict[str, str] | None = None, body: bytes | None = None) -> Any:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    request_headers.update(headers or {})
    request = Request(url, data=body, headers=request_headers, method="POST" if body else "GET")
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise ProviderError(f"Request failed for {url}: {exc}") from exc


class BBCNewsProvider:
    """Read BBC's attributed RSS feed; check BBC terms for your intended use."""

    DEFAULT_URL = "https://feeds.bbci.co.uk/news/business/rss.xml"

    def __init__(self, feed_url: str = DEFAULT_URL):
        self.feed_url = feed_url

    def fetch(self, limit: int = 20) -> list[NewsItem]:
        request = Request(self.feed_url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=15) as response:
                root = ElementTree.fromstring(response.read())
        except Exception as exc:
            raise ProviderError(f"BBC RSS request failed: {exc}") from exc
        return [
            NewsItem(
                headline=(node.findtext("title") or "").strip(),
                source="BBC News",
                url=node.findtext("link"),
                published_at=node.findtext("pubDate"),
            )
            for node in root.findall("./channel/item")[:limit]
            if node.findtext("title")
        ]


class FTNewsProvider:
    """FT headline search adapter. Requires an appropriately licensed API key."""

    URL = "https://api.ft.com/content/search/v1"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("FT_API_KEY")

    def fetch(self, query: str = "markets", limit: int = 20) -> list[NewsItem]:
        if not self.api_key:
            raise ProviderError("Set FT_API_KEY to use the licensed FT Content API")
        payload = json.dumps({
            "queryString": query,
            "resultContext": {"maxResults": limit, "aspects": ["title", "lifecycle", "location"]},
        }).encode("utf-8")
        data = _request_json(
            self.URL,
            headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"},
            body=payload,
        )
        results = data.get("results", [{}])[0].get("results", [])
        items = []
        for row in results[:limit]:
            title = row.get("title", {}).get("title") or row.get("title")
            location = row.get("location", {})
            lifecycle = row.get("lifecycle", {})
            if title:
                items.append(NewsItem(str(title), "Financial Times", location.get("uri"), lifecycle.get("lastPublishDateTime")))
        return items


class KalshiProvider:
    BASE_URL = "https://external-api.kalshi.com/trade-api/v2"

    def fetch(self, limit: int = 100, status: str = "open") -> list[PredictionMarket]:
        url = f"{self.BASE_URL}/markets?{urlencode({'limit': limit, 'status': status})}"
        rows = _request_json(url).get("markets", [])
        output = []
        for row in rows:
            cents = row.get("yes_bid")
            dollars = row.get("yes_bid_dollars")
            probability = float(dollars) if dollars is not None else (float(cents) / 100 if cents is not None else None)
            output.append(PredictionMarket(
                str(row.get("ticker", "")),
                str(row.get("title", "")),
                probability,
                _as_float(row.get("volume_fp", row.get("volume"))),
                "Kalshi",
            ))
        return output


class PolymarketProvider:
    URL = "https://gamma-api.polymarket.com/markets"

    def fetch(self, limit: int = 100, active: bool = True) -> list[PredictionMarket]:
        url = f"{self.URL}?{urlencode({'limit': limit, 'active': str(active).lower(), 'closed': 'false'})}"
        rows = _request_json(url)
        output = []
        for row in rows:
            prices = row.get("outcomePrices", [])
            if isinstance(prices, str):
                try:
                    prices = json.loads(prices)
                except json.JSONDecodeError:
                    prices = []
            probability = _as_float(prices[0]) if prices else None
            output.append(PredictionMarket(
                str(row.get("id", "")),
                str(row.get("question", "")),
                probability,
                _as_float(row.get("volume")),
                "Polymarket",
            ))
        return output


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
