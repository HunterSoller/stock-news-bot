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
# Environment / Telegram Setup
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
# Time Window (ET)
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
# Keywords & Sentiment Logic
# ================================
bullish_keywords = [
    "beats", "surge", "record", "growth", "strong", "rises", "profit",
    "upgraded", "outperforms", "soars", "jumps", "tops", "rallies"
]
bearish_keywords = [
    "misses", "drops", "falls", "decline", "loss", "downgraded",
    "weak", "plunge", "disappoints", "warns", "cut", "reduces"
]

BLACKLIST = {"USD", "FOMC", "AI", "CEO", "ETF", "IPO", "EV", "FDA", "EPS", "GDP", "SEC"}

def classify_sentiment(title: str) -> str:
    tl = title.lower()
    b_score = sum(1 for kw in bullish_keywords if kw in tl)
    s_score = sum(1 for kw in bearish_keywords if kw in tl)
    if b_score > s_score:
        return "BULLISH"
    elif s_score > b_score:
        return "BEARISH"
    else:
        return "NEUTRAL"

def clean(text: str) -> str:
    return text.strip()

def extract_ticker(title: str) -> str:
    # Simple heuristic: uppercase words 2–5 letters not blacklisted
    for part in title.split():
        p = part.strip().upper()
        if p.isalpha() and 2 <= len(p) <= 5 and p not in BLACKLIST:
            return p
    return None

# ================================
# Scanning & Messaging
# ================================
def scan_and_send(feeds, force_bio=False):
    seen = set()
    items = []
    for url in feeds:
        feed = feedparser.parse(url)
        for e in feed.entries:
            title = clean(e.get("title", ""))
            if not title or title in seen:
                continue
            seen.add(title)

            # Only consider if keyword present
            if not any(kw in title.lower() for kw in bullish_keywords + bearish_keywords):
                continue

            link = e.get("link", "").strip()
            ticker = extract_ticker(title)

            items.append((title, link, ticker))
            # Send immediately
            label = classify_sentiment(title)
            msg_text = f"*{label}* {'$'+ticker if ticker else ''}\n{title}\n{link}"
            # Decide which chat
            chat_id = TG_BIOTECH if force_bio and TG_BIOTECH else TG_MARKET
            resp = session.post(TG_API, json={"chat_id": chat_id, "text": msg_text, "parse_mode": "Markdown"}, timeout=10)
            print("Telegram send response:", resp.status_code, resp.text)

    return items

def in_window(now_dt):
    return WINDOW_START <= now_dt.time() <= WINDOW_END

def main_loop():
    global BRIEF_SENT_DATE
    BRIEF_SENT_DATE = None
    while True:
        now = dt.now(ET)
        # Send morning brief once per day
        if now.hour == BRIEF_HOUR and BRIEF_SENT_DATE != now.date():
            m_items = scan_and_send(FEEDS_MARKET)
            b_items = scan_and_send(FEEDS_BIOTECH, force_bio=True)
            BRIEF_SENT_DATE = now.date()

        # During window, continuously scan
        elif in_window(now):
            scan_and_send(FEEDS_MARKET)
            scan_and_send(FEEDS_BIOTECH, force_bio=True)

        time.sleep(60)

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        print("\n✅ Running in TEST mode: Sending one-time test messages")
        test_m = [("Test Market Headline", "https://example.com", "TST")]
        test_b = [("Test Bio Headline", "https://example.com", "BIO")]
        for t, link, ticker in test_m:
            msg = f"*{classify_sentiment(t)}* ${ticker}\n{t}\n{link}"
            resp = session.post(TG_API, json={"chat_id": TG_MARKET, "text": msg, "parse_mode": "Markdown"}, timeout=10)
            print("Telegram send response:", resp.status_code, resp.text)
        for t, link, ticker in test_b:
            msg = f"*{classify_sentiment(t)}* ${ticker}\n{t}\n{link}"
            resp = session.post(TG_API, json={"chat_id": TG_BIOTECH, "text": msg, "parse_mode": "Markdown"}, timeout=10)
            print("Telegram send response:", resp.status_code, resp.text)
        print("\n✅ Test messages sent")
    else:
        main_loop()
