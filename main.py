# main.py

from dotenv import load_dotenv
load_dotenv()

import os
import time
import re
import feedparser
import requests
from datetime import datetime as dt, time as dtime, timedelta
from dateutil.tz import gettz
from requests.adapters import HTTPAdapter, Retry

# ----------------------------
# Telegram / Environment Setup
# ----------------------------
TG_TOKEN   = os.getenv("TG_BOT_TOKEN", "").strip()
TG_MARKET  = os.getenv("TG_CHAT_ID", "").strip()
TG_BIOTECH = os.getenv("TG_BIOTECH_CHAT_ID", "").strip()

if not TG_TOKEN or not TG_MARKET:
    raise SystemExit("Missing TG_BOT_TOKEN or TG_CHAT_ID env var.")

TG_API = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

# ----------------------------
# Time Window Configuration
# ----------------------------
ET = gettz("America/New_York")
WINDOW_START = dtime(7, 0)
WINDOW_END   = dtime(20, 0)
BRIEF_HOUR = 9
BRIEF_SENT_DATE = None

# Delay between batches
BATCH_DELAY = timedelta(minutes=6)

# ----------------------------
# RSS Feeds
# ----------------------------
FEEDS_MARKET = [
    "https://www.cnbc.com/id/15839135/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.investing.com/rss/news.rss",
]
FEEDS_BIOTECH = [
    "https://www.fiercebiotech.com/rss.xml",
    "https://www.biospace.com/rss",
]

# ----------------------------
# Keywords & Sentiment Logic
# ----------------------------
BULLISH = ["beats", "tops", "rises", "surges", "jumps", "soars", "outperforms", "upgraded"]
BEARISH = ["misses", "falls", "drops", "declines", "downgraded", "warns", "cuts", "sinks"]
ALL_KEYWORDS = BULLISH + BEARISH

BLACKLIST = {"USD", "FOMC", "ETF", "IPO", "AI", "GDP", "CEO", "EV", "SEC", "FDA"}

TICKER_REGEX = re.compile(r"\$([A-Z]{2,5})|\(([A-Z]{2,5})\)")

def clean(text: str) -> str:
    return text.replace("\n", " ").strip()

def classify_sentiment(title: str) -> str:
    tl = title.lower()
    b = sum(tl.count(w) for w in BULLISH)
    s = sum(tl.count(w) for w in BEARISH)
    if b >= s + 2:
        return "BULLISH"
    elif s >= b + 2:
        return "BEARISH"
    else:
        return "NEUTRAL"

def extract_ticker(title: str) -> str | None:
    m = TICKER_REGEX.search(title)
    if m:
        tick = (m.group(1) or m.group(2)).upper()
        if 2 <= len(tick) <= 5 and tick not in BLACKLIST:
            return tick
    # fallback: uppercase 2–5 letters
    for w in re.findall(r"\b[A-Z]{2,5}\b", title):
        if w not in BLACKLIST:
            return w
    return None

def is_relevant(title: str) -> bool:
    tl = title.lower()
    return any(w in tl for w in ALL_KEYWORDS)

def importance_score(title: str) -> int:
    tl = title.lower()
    score = 0
    for w in BULLISH:
        score += tl.count(w) * 2
    for w in BEARISH:
        score += tl.count(w) * 2
    extras = ["earnings", "guidance", "forecast", "outlook", "revenue"]
    for e in extras:
        if e in tl:
            score += 1
    return score

# ----------------------------
# Caching & Control Variables
# ----------------------------
sent_global = set()  # store (title, link)
last_batch_time = None

def send_telegram(msg: str, chat_id: str):
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    try:
        r = session.post(TG_API, json=payload, timeout=10)
        print("Telegram:", r.status_code, r.text[:200])
    except Exception as e:
        print("Telegram send error:", e)

def scan_and_collect(feeds, is_bio: bool):
    items = []
    for url in feeds:
        feed = feedparser.parse(url)
        for e in feed.entries:
            title = clean(e.get("title", ""))
            link  = e.get("link", "")
            key = (title, link)
            if not title or key in sent_global:
                continue
            if not is_relevant(title):
                continue
            ticker = extract_ticker(title)
            if not ticker:
                continue
            score = importance_score(title)
            if score < 4:
                continue
            sentiment = classify_sentiment(title)
            if sentiment == "NEUTRAL":
                continue
            items.append((score, sentiment, title, ticker, link, is_bio))
    return items

def send_batch_alerts(collected):
    global last_batch_time
    if not collected:
        return
    now = dt.now(ET)
    if last_batch_time and (now - last_batch_time) < BATCH_DELAY:
        print("Batch delay not passed; skipping send.")
        return
    collected.sort(key=lambda x: x[0], reverse=True)
    top4 = collected[:4]
    for score, sentiment, title, ticker, link, is_bio in top4:
        chat = TG_BIOTECH if (is_bio and TG_BIOTECH) else TG_MARKET
        msg = f"*{sentiment}* ${ticker}\n{title}\n{link}"
        send_telegram(msg, chat)
        sent_global.add((title, link))
        time.sleep(2)
    last_batch_time = now

def in_window(now_dt):
    return WINDOW_START <= now_dt.time() <= WINDOW_END

def main_loop():
    global BRIEF_SENT_DATE
    BRIEF_SENT_DATE = None
    print("Bot starting with tightened rules.")
    while True:
        now = dt.now(ET)
        if now.hour == BRIEF_HOUR and BRIEF_SENT_DATE != now.date():
            market_items = scan_and_collect(FEEDS_MARKET, False)
            bio_items = scan_and_collect(FEEDS_BIOTECH, True)
            send_batch_alerts(market_items + bio_items)
            BRIEF_SENT_DATE = now.date()
        elif in_window(now):
            market_items = scan_and_collect(FEEDS_MARKET, False)
            bio_items = scan_and_collect(FEEDS_BIOTECH, True)
            send_batch_alerts(market_items + bio_items)
        else:
            time.sleep(600)
        time.sleep(120)

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        print("Running test mode...")
        msg = "*BULLISH* $TEST\nThis is a test alert.\nhttps://example.com"
        send_telegram(msg, TG_MARKET)
        send_telegram(msg, TG_BIOTECH)
    else:
        main_loop()
def manual_trigger():
    # Example custom test that meets your filters
    title = "Company X surges 50% after record earnings"
    link = "https://example.com/record-earnings"
    ticker = "COMPX"
    sentiment = "BULLISH"
    msg = f"*{sentiment}* ${ticker}\n{title}\n{link}"
    send_telegram(msg, TG_MARKET)
    # And also for biotech if you want:
    send_telegram(msg, TG_BIOTECH)

if __name__ == "__main__":
    import sys
    if "--manual" in sys.argv:
        manual_trigger()
    else:
        main_loop()
