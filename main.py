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

BATCH_INTERVAL = timedelta(minutes=6)
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
TICKER_REGEX = re.compile(r"\\$([A-Z]{2,5})|\\(([A-Z]{2,5})\\)")
BLACKLIST = {"USD", "FOMC", "ETF", "IPO", "AI", "GDP", "CEO", "EV", "SEC", "FDA"}

sent_global = set()
ticker_sector_cache = {}
last_batch_time = None

def clean(text):
    return text.replace("\n", " ").strip()

def extract_ticker(title):
    m = TICKER_REGEX.search(title)
    if m:
        t = (m.group(1) or m.group(2)).upper()
        if 2 <= len(t) <= 5 and t not in BLACKLIST:
            return t
    for w in re.findall(r"\\b[A-Z]{2,5}\\b", title):
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

def get_sector(ticker):
    if ticker in ticker_sector_cache:
        return ticker_sector_cache[ticker]
    try:
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "").lower()
        ticker_sector_cache[ticker] = sector
        return sector
    except:
        return ""

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
        print(f"[Telegram] {chat_id}: {r.status_code}")
    except Exception as e:
        print("[ERROR] Telegram send failed:", e)

def scan_feeds():
    items = []
    feeds = [(FEEDS_MARKET, False), (FEEDS_BIOTECH, True)]
    for feed_list, is_bio in feeds:
        for url in feed_list:
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
    return items

def send_batch():
    global last_batch_time
    now = dt.now(ET)
    if last_batch_time and now - last_batch_time < BATCH_INTERVAL:
        print("[WAIT] Too soon. Skipping batch.")
        return

    headlines = scan_feeds()
    if not headlines:
        print("[INFO] No headlines, skipping.")
        return

    headlines.sort(key=lambda x: x[0], reverse=True)
    top = headlines[:5]

    for score, sentiment, title, ticker, link in top:
        sector = get_sector(ticker)
        is_bio = any(x in sector for x in ["biotech", "pharma", "health"])
        chat = TG_BIOTECH if is_bio and TG_BIOTECH else TG_MARKET
        msg = f"*{sentiment}* ${ticker}\n{title}\n{link}"
        send_telegram(msg, chat)
        sent_global.add((title, link))
        time.sleep(1)

    last_batch_time = now

def main():
    print("[STARTED] Bot active. Pulling every 6 minutes.")
    while True:
        try:
            send_batch()
        except Exception as e:
            print("[ERROR] Main loop exception:", e)
        time.sleep(360)

if __name__ == "__main__":
    main()
