# main.py

from dotenv import load_dotenv
load_dotenv()

import os
import time
import re
import feedparser
import requests
from datetime import datetime as dt, time as dtime
from dateutil.tz import gettz
from requests.adapters import HTTPAdapter, Retry

# ============== Telegram / Config ===============
TG_TOKEN   = os.getenv("TG_BOT_TOKEN", "").strip()
TG_MARKET  = os.getenv("TG_CHAT_ID", "").strip()
TG_BIOTECH = os.getenv("TG_BIOTECH_CHAT_ID", "").strip()

if not TG_TOKEN or not TG_MARKET:
    raise SystemExit("Missing TG_BOT_TOKEN or TG_CHAT_ID")

TG_API = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

# ============== Time / Window ===============
ET = gettz("America/New_York")
WINDOW_START = dtime(7, 0)
WINDOW_END   = dtime(20, 0)
BRIEF_HOUR = 9
BRIEF_SENT_DATE = None

# ============== RSS Feeds ===============
FEEDS_MARKET = [
    "https://www.cnbc.com/id/15839135/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.investing.com/rss/news.rss",
]
FEEDS_BIOTECH = [
    "https://www.fiercebiotech.com/rss.xml",
    "https://www.biospace.com/rss",
]

# ============== Filtering & Sentiment ===============
BULLISH = ["beats", "tops", "rises", "surges", "jumps", "soars", "outperforms", "upgraded"]
BEARISH = ["misses", "falls", "drops", "declines", "downgraded", "warns", "cuts", "sinks"]
ALL_KEYWORDS = BULLISH + BEARISH

BLACKLIST = {"USD", "FOMC", "ETF", "IPO", "AI", "GDP", "CEO", "EV", "SEC", "FDA"}

TICKER_REGEX = re.compile(r"\$([A-Z]{2,5})|\(([A-Z]{2,5})\)")

def clean(text: str) -> str:
    return text.replace("\n", " ").strip()

def classify_sentiment(title: str) -> str:
    tl = title.lower()
    b = sum(1 for w in BULLISH if w in tl)
    s = sum(1 for w in BEARISH if w in tl)
    if b > s + 1:  # require stronger bias
        return "BULLISH"
    if s > b + 1:
        return "BEARISH"
    return "NEUTRAL"

def extract_ticker(title: str) -> str | None:
    # First try explicit patterns
    m = TICKER_REGEX.search(title)
    if m:
        t = (m.group(1) or m.group(2)).upper()
        if 2 <= len(t) <= 5:
            return t
    # Fallback: uppercase standalone word, but only if it appears in parentheses or after space
    for word in re.findall(r"\b[A-Z]{2,5}\b", title):
        if word not in BLACKLIST:
            return word
    return None

def is_relevant(title: str) -> bool:
    tl = title.lower()
    # Must contain at least one strong move keyword
    if not any(w in tl for w in ALL_KEYWORDS):
        return False
    # Exclude very common neutral words
    if "company reports" in tl and ("mixed" in tl or "quarter" in tl and "rise" not in tl and "fall" not in tl):
        return False
    return True

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

sent_cache = set()

def send_telegram(msg: str, chat_id: str):
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    try:
        r = session.post(TG_API, json=payload, timeout=10)
        print("Telegram:", r.status_code, r.text[:200])
    except Exception as e:
        print("Telegram send error:", e)

def scan_feeds(feeds, force_bio=False):
    for url in feeds:
        feed = feedparser.parse(url)
        for e in feed.entries:
            title = clean(e.get("title", ""))
            link = e.get("link", "")
            if not title or (title, link) in sent_cache:
                continue

            if not is_relevant(title):
                continue

            ticker = extract_ticker(title)
            if not ticker:
                continue

            score = importance_score(title)
            if score < 4:  # raise threshold further
                continue

            sentiment = classify_sentiment(title)
            msg = f"*{sentiment}* ${ticker}\n{title}\n{link}"
            chat_id = TG_BIOTECH if (force_bio and TG_BIOTECH) else TG_MARKET
            send_telegram(msg, chat_id)

            sent_cache.add((title, link))
            # Optionally: clean up cache if too big
            if len(sent_cache) > 5000:
                sent_cache.clear()
            time.sleep(1)

def in_window(now_dt):
    return WINDOW_START <= now_dt.time() <= WINDOW_END

def main_loop():
    global BRIEF_SENT_DATE
    BRIEF_SENT_DATE = None
    print("Bot started.")
    while True:
        now = dt.now(ET)
        if now.hour == BRIEF_HOUR and BRIEF_SENT_DATE != now.date():
            scan_feeds(FEEDS_MARKET)
            scan_feeds(FEEDS_BIOTECH, force_bio=True)
            BRIEF_SENT_DATE = now.date()
        elif in_window(now):
            scan_feeds(FEEDS_MARKET)
            scan_feeds(FEEDS_BIOTECH, force_bio=True)
        else:
            time.sleep(600)
        time.sleep(180)

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        print("Running TEST mode")
        msg = "*BULLISH* $TEST\nHigh confidence test headline\nhttps://example.com"
        send_telegram(msg, TG_MARKET)
        send_telegram(msg, TG_BIOTECH)
    else:
        main_loop()
