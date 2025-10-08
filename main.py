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

# ========================
# Configuration / Telegram
# ========================
TG_TOKEN   = os.getenv("TG_BOT_TOKEN", "").strip()
TG_MARKET  = os.getenv("TG_CHAT_ID", "").strip()
TG_BIOTECH = os.getenv("TG_BIOTECH_CHAT_ID", "").strip()

if not TG_TOKEN or not TG_MARKET:
    raise SystemExit("Missing TG_BOT_TOKEN or TG_CHAT_ID")

TG_API = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504])
session.mount("https://", HTTPAdapter(max_retries=retries))

# ===================================
# Time / operational window settings
# ===================================
ET = gettz("America/New_York")
WINDOW_START = dtime(7, 0)
WINDOW_END   = dtime(20, 0)
BRIEF_HOUR = 9
BRIEF_SENT_DATE = None

# Batch delay: wait this long between sending batches
BATCH_DELAY = timedelta(minutes=10)

# =================
# RSS feed sources
# =================
FEEDS_MARKET = [
    "https://www.cnbc.com/id/15839135/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.investing.com/rss/news.rss",
]
FEEDS_BIOTECH = [
    "https://www.fiercebiotech.com/rss.xml",
    "https://www.biospace.com/rss",
]

# ==========================
# Keywords & sentiment logic
# ==========================
BULLISH = ["beats", "tops", "rises", "surges", "jumps", "soars", "outperforms", "upgraded"]
BEARISH = ["misses", "falls", "drops", "declines", "downgraded", "warns", "cuts", "sinks"]
ALL_KEYWORDS = BULLISH + BEARISH

BLACKLIST = {"USD","FOMC","ETF","IPO","AI","GDP","CEO","EV","SEC","FDA"}

TICKER_REGEX = re.compile(r"\$([A-Z]{2,5})|\(([A-Z]{2,5})\)")

def clean(text: str) -> str:
    return text.replace("\n", " ").strip()

def classify_sentiment(title: str) -> str:
    tl = title.lower()
    b = sum(1 for w in BULLISH if w in tl)
    s = sum(1 for w in BEARISH if w in tl)
    # require decent margin
    if b >= s + 2:
        return "BULLISH"
    elif s >= b + 2:
        return "BEARISH"
    return "NEUTRAL"

def extract_ticker(title: str) -> str | None:
    m = TICKER_REGEX.search(title)
    if m:
        tick = (m.group(1) or m.group(2)).upper()
        # ensure not blacklisted
        if 2 <= len(tick) <= 5 and tick not in BLACKLIST:
            return tick
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

# ================
# State & caching
# ================
sent_global = set()  # (title, link) pairs already sent
last_batch_time = None

def send_telegram(msg: str, chat_id: str):
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    try:
        r = session.post(TG_API, json=payload, timeout=10)
        print("Telegram:", r.status_code, r.text[:200])
    except Exception as e:
        print("Telegram send error:", e)

def scan_and_collect(feeds):
    collected = []
    for url in feeds:
        feed = feedparser.parse(url)
        for e in feed.entries:
            title = clean(e.get("title", ""))
            link = e.get("link", "")
            if not title or (title, link) in sent_global:
                continue
            if not is_relevant(title):
                continue
            ticker = extract_ticker(title)
            if not ticker:
                continue
            score = importance_score(title)
            if score < 4:  # require minimum significance
                continue
            sentiment = classify_sentiment(title)
            # skip neutral sentiments
            if sentiment == "NEUTRAL":
                continue
            collected.append((title, link, ticker, sentiment, score))
    return collected

def send_batch_alerts(collected, is_bio=False):
    global last_batch_time
    if not collected:
        return

    # Sort by descending score (highest first)
    collected.sort(key=lambda x: x[4], reverse=True)
    top5 = collected[:5]

    # Wait between batches
    now = dt.now(ET)
    if last_batch_time and (now - last_batch_time) < BATCH_DELAY:
        print("Batch delay not passed; skipping batch send")
        return

    for (title, link, ticker, sentiment, score) in top5:
        msg = f"*{sentiment}* ${ticker}\n{title}\n{link}"
        chat = TG_BIOTECH if (is_bio and TG_BIOTECH) else TG_MARKET
        send_telegram(msg, chat)
        sent_global.add((title, link))
        time.sleep(2)  # small pause between sends

    last_batch_time = now

def in_window(now_dt):
    return WINDOW_START <= now_dt.time() <= WINDOW_END

def main_loop():
    global BRIEF_SENT_DATE, last_batch_time
    BRIEF_SENT_DATE = None
    last_batch_time = None
    print("Bot running with stricter filters.")
    while True:
        now = dt.now(ET)
        if now.hour == BRIEF_HOUR and BRIEF_SENT_DATE != now.date():
            m = scan_and_collect(FEEDS_MARKET)
            b = scan_and_collect(FEEDS_BIOTECH)
            send_batch_alerts(m, False)
            send_batch_alerts(b, True)
            BRIEF_SENT_DATE = now.date()
        elif in_window(now):
            m = scan_and_collect(FEEDS_MARKET)
            b = scan_and_collect(FEEDS_BIOTECH)
            send_batch_alerts(m, False)
            send_batch_alerts(b, True)
        else:
            time.sleep(600)

        time.sleep(120)

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        print("Running test mode")
        msg = "*BULLISH* $TEST\nOnly important test\nhttps://example.com"
        send_telegram(msg, TG_MARKET)
        send_telegram(msg, TG_BIOTECH)
    else:
        main_loop()
