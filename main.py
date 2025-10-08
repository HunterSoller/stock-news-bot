# main.py
from dotenv import load_dotenv
load_dotenv()

import os
import time
import feedparser
import requests
from datetime import datetime as dt, time as dtime
from dateutil.tz import gettz
from requests.adapters import HTTPAdapter, Retry

# ================================
# Telegram & Environment
# ================================
TG_TOKEN   = os.getenv("TG_BOT_TOKEN", "").strip()
TG_MARKET  = os.getenv("TG_CHAT_ID", "").strip()
TG_BIOTECH = os.getenv("TG_BIOTECH_CHAT_ID", "").strip()

if not TG_TOKEN or not TG_MARKET:
    raise SystemExit("Missing TG_BOT_TOKEN or TG_CHAT_ID env var.")

TG_API = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

# ================================
# Time window (Eastern Time)
# ================================
ET = gettz("America/New_York")
WINDOW_START = dtime(7, 0)
WINDOW_END   = dtime(20, 0)
BRIEF_HOUR = 9
BRIEF_SENT_DATE = None

# ================================
# RSS Feeds
# ================================
FEEDS_MARKET = [
    "https://www.cnbc.com/id/15839135/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories"
]

FEEDS_BIOTECH = [
    "https://www.fiercebiotech.com/rss.xml",
    "https://www.biospace.com/rss"
]

# ================================
# Keywords for filtering and sentiment
# ================================
BULLISH_KEYWORDS = [
    "beats", "surge", "record", "growth", "strong", "rises",
    "profit", "upgraded", "soars", "jumps", "tops", "rallies", "outperforms"
]
BEARISH_KEYWORDS = [
    "misses", "drops", "falls", "decline", "loss", "downgraded",
    "weak", "plunge", "disappoints", "warns", "cut", "reduces", "sinks"
]
ALL_KEYWORDS = BULLISH_KEYWORDS + BEARISH_KEYWORDS

BLACKLIST = {"USD", "FOMC", "AI", "CEO", "ETF", "IPO", "EV", "FDA", "EPS", "GDP", "SEC"}

def classify_sentiment(title: str) -> str:
    tl = title.lower()
    b_score = sum(1 for kw in BULLISH_KEYWORDS if kw in tl)
    s_score = sum(1 for kw in BEARISH_KEYWORDS if kw in tl)
    if b_score > s_score:
        return "BULLISH"
    elif s_score > b_score:
        return "BEARISH"
    else:
        return "NEUTRAL"

def extract_ticker(title: str) -> str:
    # Improved heuristic: look for $TICKER or uppercase words
    parts = title.split()
    for part in parts:
        # if starts with $ and valid length
        if part.startswith("$") and len(part) <= 6:
            t = part[1:].upper()
            if t.isalpha() and 1 < len(t) <= 5 and t not in BLACKLIST:
                return t
        # fallback: if it's uppercase and 2-5 letters
        p = part.upper().strip(",.;:")
        if p.isalpha() and 1 < len(p) <= 5 and p not in BLACKLIST:
            return p
    return None

def clean(text: str) -> str:
    return text.strip()

# ================================
# Scanning, Filtering, Sending
# ================================
def scan_and_send(feeds, force_bio=False):
    seen = set()
    results = []
    for feed_url in feeds:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = clean(entry.get("title", ""))
            if not title or title in seen:
                continue
            seen.add(title)

            tl = title.lower()
            # require at least one keyword AND a ticker
            if not any(kw in tl for kw in ALL_KEYWORDS):
                continue

            ticker = extract_ticker(title)
            if not ticker:
                continue  # skip if no ticker

            link = entry.get("link", "").strip()
            label = classify_sentiment(title)
            msg = f"*{label}* ${ticker}\n{title}\n{link}"

            chat_id = TG_BIOTECH if force_bio and TG_BIOTECH else TG_MARKET
            resp = session.post(TG_API, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=10)
            print("Telegram send response:", resp.status_code, resp.text)

            results.append((title, link, ticker))
    return results

def in_window(now_dt):
    return WINDOW_START <= now_dt.time() <= WINDOW_END

def main_loop():
    global BRIEF_SENT_DATE
    BRIEF_SENT_DATE = None
    while True:
        now = dt.now(ET)
        if now.hour == BRIEF_HOUR and BRIEF_SENT_DATE != now.date():
            scan_and_send(FEEDS_MARKET)
            scan_and_send(FEEDS_BIOTECH, force_bio=True)
            BRIEF_SENT_DATE = now.date()
        elif in_window(now):
            scan_and_send(FEEDS_MARKET)
            scan_and_send(FEEDS_BIOTECH, force_bio=True)
        time.sleep(60)

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        print("\n✅ Running in TEST mode")
        test_items = [("Test Headline $TEST", "https://example.com", "TEST")]
        for (t, link, ticker) in test_items:
            label = classify_sentiment(t)
            msg = f"*{label}* ${ticker}\n{t}\n{link}"
            resp = session.post(TG_API, json={"chat_id": TG_MARKET, "text": msg, "parse_mode": "Markdown"}, timeout=10)
            print("Telegram send response:", resp.status_code, resp.text)
        print("✅ Test done")
    else:
        main_loop()
