from dotenv import load_dotenv
load_dotenv()

import os
import time
import re
import feedparser
import requests
import yfinance as yf
import sys
from datetime import datetime as dt, timedelta, time as dtime
from dateutil.tz import gettz
from requests.adapters import HTTPAdapter, Retry

# ================ CONFIG ================
TG_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
TG_MARKET = os.getenv("TG_CHAT_ID", "").strip()
TG_BIOTECH = os.getenv("TG_BIOTECH_CHAT_ID", "").strip()
TG_API = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

if not TG_TOKEN or not TG_MARKET:
    raise SystemExit("Missing Telegram configuration.")

session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

ET = gettz("America/New_York")
WINDOW_START = dtime(7, 0)
WINDOW_END = dtime(20, 0)
BRIEF_HOUR = 9
BRIEF_SENT_DATE = None

BATCH_INTERVAL = timedelta(minutes=3)
FEEDS_MARKET = [
    "https://www.cnbc.com/id/15839135/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.investing.com/rss/news.rss",
]
FEEDS_BIOTECH = [
    "https://www.fiercebiotech.com/rss.xml",
    "https://www.biospace.com/rss",
]

BULLISH = ["beats", "tops", "rises", "surges", "jumps", "soars", "outperforms", "upgraded", "merger", "acquisition"]
BEARISH = ["misses", "falls", "drops", "declines", "downgraded", "warns", "cuts", "sinks", "bankruptcy", "lawsuit"]
ALL_KEYWORDS = BULLISH + BEARISH
TICKER_REGEX = re.compile(r"\$([A-Z]{2,5})|\(([A-Z]{2,5})\)|\b([A-Z]{2,5})\b")
BLACKLIST = {
    "USD", "FOMC", "ETF", "IPO", "AI", "GDP", "CEO", "EV", "SEC", "FDA",
    "US", "DOJ", "IRS", "NYT", "CNBC", "UK", "EU", "UAW", "WSJ", "FBI", "CNN",
    "WSB", "CPI", "PPI", "OPEC", "UN", "NATO"
}

sent_global = set()
ticker_sector_cache = {}
last_batch_time = None

def clean(text):
    return text.replace("\n", " ").strip()

def extract_ticker(title):
    matches = TICKER_REGEX.findall(title)
    for g1, g2, g3 in matches:
        tick = g1 or g2 or g3
        if tick and 2 <= len(tick) <= 5 and tick.upper() not in BLACKLIST:
            return tick.upper()
    return None

def classify_sentiment(title):
    tl = title.lower()
    b = sum(tl.count(w) for w in BULLISH)
    s = sum(tl.count(w) for w in BEARISH)
    if b > s:
        return "BULLISH"
    elif s > b:
        return "BEARISH"
    return "NEUTRAL"

def importance_score(title):
    tl = title.lower()
    score = 0
    for w in BULLISH:
        score += tl.count(w) * 2
    for w in BEARISH:
        score += tl.count(w) * 2
    for extra in ["earnings", "guidance", "outlook", "forecast", "merger", "acquisition"]:
        if extra in tl:
            score += 1
    return score

def send_telegram(msg, chat_id):
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    try:
        r = session.post(TG_API, json=payload, timeout=10)
        print(f"[SENT] {chat_id}: {msg[:80]}...")
        sys.stdout.flush()
    except Exception as e:
        print("[ERROR] Telegram send failed:", e)
        sys.stdout.flush()

def scan_and_filter(feeds):
    items = []
    for url in feeds:
        feed = feedparser.parse(url)
        for e in feed.entries:
            title = clean(e.get("title", ""))
            link = e.get("link", "")
            key = (title, link)
            if not title or key in sent_global:
                continue
            ticker = extract_ticker(title)
            if not ticker:
                continue
            sentiment = classify_sentiment(title)
            if sentiment == "NEUTRAL":
                continue
            score = importance_score(title)
            items.append((score, sentiment, title, ticker, link))
    return sorted(items, key=lambda x: x[0], reverse=True)[:5]

def send_batch():
    market_alerts = scan_and_filter(FEEDS_MARKET)
    biotech_alerts = scan_and_filter(FEEDS_BIOTECH)

    for score, sentiment, title, ticker, link in market_alerts:
        msg = f"*{sentiment}* ${ticker}\n{title}\n{link}"
        send_telegram(msg, TG_MARKET)
        sent_global.add((title, link))
        time.sleep(1)

    for score, sentiment, title, ticker, link in biotech_alerts:
        msg = f"*{sentiment}* ${ticker}\n{title}\n{link}"
        send_telegram(msg, TG_BIOTECH)
        sent_global.add((title, link))
        time.sleep(1)

def send_morning_digest():
    all_alerts = scan_and_filter(FEEDS_MARKET + FEEDS_BIOTECH)
    if not all_alerts:
        return
    message = "🌅 *Good Morning!* 4 stocks to watch today:\n\n"
    for score, sentiment, title, ticker, link in all_alerts[:4]:
        message += f"*{sentiment}* ${ticker}: {title}\n{link}\n\n"
    send_telegram(message.strip(), TG_MARKET)
    if TG_BIOTECH:
        send_telegram(message.strip(), TG_BIOTECH)

def in_window(now):
    return WINDOW_START <= now.time() <= WINDOW_END

def is_weekday(now):
    return now.weekday() < 5

def main():
    global BRIEF_SENT_DATE
    print("[BOOT] Stock Alert Bot running 7am–8pm ET, Mon–Fri")
    sys.stdout.flush()
    while True:
        now = dt.now(ET)
        try:
            if is_weekday(now):
                if now.hour == BRIEF_HOUR and BRIEF_SENT_DATE != now.date():
                    print("[DIGEST] Sending morning digest")
                    sys.stdout.flush()
                    send_morning_digest()
                    BRIEF_SENT_DATE = now.date()

                if in_window(now):
                    print("[BATCH] Sending alerts...")
                    sys.stdout.flush()
                    send_batch()
                else:
                    print(f"[IDLE] Outside trading hours at {now.time()}")
                    sys.stdout.flush()
            else:
                print("[WEEKEND] Sleeping 1 hour")
                sys.stdout.flush()
                time.sleep(3600)
        except Exception as e:
            print("[ERROR]", e)
            sys.stdout.flush()
        time.sleep(180)

if __name__ == "__main__":
    main()
