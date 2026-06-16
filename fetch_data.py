"""Fetch free tech/semiconductor/AI stock data via yfinance (no LLM API, no key).

Pulls 5-day price/volume for a chips + AI watchlist, computes % change and
volume-vs-average ratio, flags notable movers, and grabs headlines for those.
Prints the whole result as JSON to stdout so a slash command can read it.
"""

import json
import sys
from datetime import datetime, timezone

import yfinance as yf


# Watchlist: chips/semis + AI/big tech
CHIPS = [
    "NVDA", "AMD", "TSM", "AVGO", "ASML", "MU", "INTC",
    "ARM", "MRVL", "QCOM", "SMCI", "LRCX", "AMAT", "KLAC",
]
AI_BIGTECH = ["MSFT", "GOOGL", "META", "AMZN", "PLTR", "ORCL"]
WATCHLIST = CHIPS + AI_BIGTECH

# Flag thresholds
PCT_MOVE_THRESHOLD = 3.0      # flag if |% change| >= 3%
VOLUME_RATIO_THRESHOLD = 1.5  # flag if volume >= 1.5x recent average


def _group_for(ticker):
    return "chips" if ticker in CHIPS else "ai_bigtech"


def get_news_headlines(ticker_obj, limit=5):
    """Read yfinance .news defensively — schema varies across versions."""
    headlines = []
    try:
        raw = ticker_obj.news or []
    except Exception:
        return headlines

    for item in raw[:limit]:
        if not isinstance(item, dict):
            continue
        # Newer yfinance nests fields under "content"; older is flat.
        content = item.get("content") if isinstance(item.get("content"), dict) else item

        title = (
            content.get("title")
            or content.get("headline")
            or item.get("title")
        )
        if not title:
            continue

        publisher = None
        prov = content.get("provider")
        if isinstance(prov, dict):
            publisher = prov.get("displayName") or prov.get("name")
        publisher = publisher or content.get("publisher") or item.get("publisher")

        link = None
        url_obj = content.get("clickThroughUrl") or content.get("canonicalUrl")
        if isinstance(url_obj, dict):
            link = url_obj.get("url")
        link = link or content.get("link") or item.get("link")

        pub_date = (
            content.get("pubDate")
            or content.get("displayTime")
            or item.get("providerPublishTime")
        )

        headlines.append({
            "title": title,
            "publisher": publisher,
            "link": link,
            "published": pub_date,
        })
    return headlines


def analyze_ticker(ticker):
    """Return a dict of metrics for one ticker, or an error entry."""
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="5d")
    except Exception as exc:
        return {"ticker": ticker, "group": _group_for(ticker), "error": str(exc)}

    if hist is None or hist.empty or len(hist) < 2:
        return {
            "ticker": ticker,
            "group": _group_for(ticker),
            "error": "insufficient price history",
        }

    closes = hist["Close"]
    volumes = hist["Volume"]

    last_close = float(closes.iloc[-1])
    prev_close = float(closes.iloc[-2])
    first_close = float(closes.iloc[0])

    pct_change_1d = ((last_close - prev_close) / prev_close * 100.0) if prev_close else 0.0
    pct_change_5d = ((last_close - first_close) / first_close * 100.0) if first_close else 0.0

    last_volume = float(volumes.iloc[-1])
    avg_volume = float(volumes.mean()) if len(volumes) else 0.0
    volume_ratio = (last_volume / avg_volume) if avg_volume else 0.0

    flagged = (abs(pct_change_1d) >= PCT_MOVE_THRESHOLD) or (volume_ratio >= VOLUME_RATIO_THRESHOLD)

    result = {
        "ticker": ticker,
        "group": _group_for(ticker),
        "last_close": round(last_close, 2),
        "prev_close": round(prev_close, 2),
        "pct_change_1d": round(pct_change_1d, 2),
        "pct_change_5d": round(pct_change_5d, 2),
        "last_volume": int(last_volume),
        "avg_volume_5d": int(avg_volume),
        "volume_ratio": round(volume_ratio, 2),
        "flagged": flagged,
        "news": [],
    }

    if flagged:
        result["news"] = get_news_headlines(tk)

    return result


def main():
    results = []
    for ticker in WATCHLIST:
        results.append(analyze_ticker(ticker))

    flagged = [r for r in results if r.get("flagged")]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "thresholds": {
            "pct_move": PCT_MOVE_THRESHOLD,
            "volume_ratio": VOLUME_RATIO_THRESHOLD,
        },
        "watchlist_count": len(WATCHLIST),
        "flagged_count": len(flagged),
        "flagged_tickers": [r["ticker"] for r in flagged],
        "results": results,
    }

    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
