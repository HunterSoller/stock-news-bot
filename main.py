from dotenv import load_dotenv
load_dotenv()

import os
import time
import re
import feedparser
import requests
import yfinance as yf
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
TICKER_REGEX = re.compile(r"\\$([A-Z]{1,5})|\\(([A-Z]{1,5})\\)")
BLACKLIST = {"USD", "FOMC", "ETF", "IPO", "AI", "GDP", "CEO", "EV", "SEC", "FDA", "US", "UK"}

sent_global = set()
ticker_sector_cache = {}


def clean(text):
    return text.replace("\n", " ").strip()

def extract_ticker(title):
    m = TICKER_REGEX.search(title)
    if m:
        t = (m.group(1) or m.group(2)).upper()
        if 1 <= len(t) <= 5 and t not in BLACKLIST:
            return t
    for w in re.findall(r"\b[A-Z]{1,5}\b", title):
        if w not in BLACKLIST:
            return w
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
    if any(x in tl for x in ["earnings", "guidance", "outlook", "forecast"]):
        score += 1
    return score

def send_telegram(msg, chat_id):
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    try:
        r = session.post(TG_API, json=payload, timeout=10)
        print(f"[SENT] To {chat_id}: {msg.splitlines()[0]}")
    except Exception as e:
        print("[ERROR] Telegram send failed:", e)

def scan_feed_list(feed_list):
    items = []
    for url in feed_list:
        feed = feedparser.parse(url)
        print(f"[FEED] {url} entries: {len(feed.entries)}")
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
    return items

def send_top_alerts():
    market_items = scan_feed_list(FEEDS_MARKET)
    biotech_items = scan_feed_list(FEEDS_BIOTECH)

    market_items.sort(key=lambda x: x[0], reverse=True)
    biotech_items.sort(key=lambda x: x[0], reverse=True)

    top_market = market_items[:5]
    top_biotech = biotech_items[:5]

    for score, sentiment, title, ticker, link in top_market:
        msg = f"*{sentiment}* ${ticker}\n{title}\n{link}"
        send_telegram(msg, TG_MARKET)
        sent_global.add((title, link))

    for score, sentiment, title, ticker, link in top_biotech:
        msg = f"*{sentiment}* ${ticker}\n{title}\n{link}"
        send_telegram(msg, TG_BIOTECH)
        sent_global.add((title, link))

def send_morning_digest():
    all_items = scan_feed_list(FEEDS_MARKET + FEEDS_BIOTECH)
    all_items.sort(key=lambda x: x[0], reverse=True)
    top_items = all_items[:4]

    if not top_items:
        return

    message = "🌅 *Good Morning!* Here are 4 stocks to watch today:\n\n"
    for score, sentiment, title, ticker, link in top_items:
        message += f"*{sentiment}* ${ticker}: {title}\n{link}\n\n"

    send_telegram(message.strip(), TG_MARKET)
    if TG_BIOTECH:
        send_telegram(message.strip(), TG_BIOTECH)

def in_window(now):
    return WINDOW_START <= now.time() <= WINDOW_END

def is_weekday(now):
    return now.weekday() < 5  # Mon–Fri

def main():
    global BRIEF_SENT_DATE
    print("[BOOT] Stock Alert Bot running 7am–8pm ET, Mon–Fri")
    while True:
        now = dt.now(ET)
        try:
            if is_weekday(now):
                if now.hour == BRIEF_HOUR and BRIEF_SENT_DATE != now.date():
                    print("[MORNING] Sending digest...")
                    send_morning_digest()
                    BRIEF_SENT_DATE = now.date()
                if in_window(now):
                    print("[BATCH] Sending alerts...")
                    send_top_alerts()
                else:
                    print(f"[SLEEP] Outside trading window at {now.time()}")
                    time.sleep(600)
            else:
                print(f"[SLEEP] Weekend ({now.strftime('%A')})")
                time.sleep(3600)
        except Exception as e:
            print("[ERROR] Main loop exception:", e)
        time.sleep(180)

if __name__ == "__main__":
    main()
