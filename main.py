# main.py
from dotenv import load_dotenv
load_dotenv()

import os
import re
import time
import json
import html
import hashlib
import feedparser
import requests

from datetime import datetime, time as dtime, timedelta
from dateutil.tz import gettz
from requests.adapters import HTTPAdapter, Retry

# =========================
#  Environment / Telegram
# =========================
TG_TOKEN   = os.getenv("TG_BOT_TOKEN", "").strip()
TG_MARKET  = os.getenv("TG_CHAT_ID", "").strip()
TG_BIOTECH = os.getenv("TG_BIOTECH_CHAT_ID", "").strip()

if not TG_TOKEN or not TG_MARKET:
    raise SystemExit("Missing TG_BOT_TOKEN or TG_CHAT_ID env var.")

TG_API = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

# =========================
#  Time window (ET)
# =========================
ET = gettz("America/New_York")
WINDOW_START = dtime(7, 0)
WINDOW_END   = dtime(20, 0)
BRIEF_HOUR = 9
BRIEF_SENT_DATE = None

# =========================
#  Ticker validation
# =========================
SYMBOLS_URLS = [
    "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
]
LAST_SYMBOLS_LOAD = None
VALID_TICKERS = set()
BLACKLIST = {"USD", "FOMC", "AI", "CEO", "ETF", "IPO", "EV", "FDA", "EPS", "GDP", "SEC", "MKT"}

# =========================
#  Feeds
# =========================
FEEDS_MARKET = [
    "https://www.cnbc.com/id/15839135/device/rss/rss.html",
    "https://www.businesswire.com/portal/site/home/news/industry/?vnsId=31372&service=Rss",
    "https://www.marketwatch.com/rss/topstories",
]

FEEDS_BIOTECH = [
    "https://www.fiercebiotech.com/rss.xml",
    "https://www.biopharmadive.com/feeds/news/",
    "https://www.medicalnewstoday.com/rss",
]

# =========================
#  Regex patterns
# =========================
MOVE_KEYWORDS = [
    "earnings", "guidance", "forecast", "raises outlook", "cuts outlook",
    "merger", "acquisition", "buyout", "takeover", "strategic review",
    "sec investigation", "doj", "lawsuit", "settlement",
    "partnership", "contract", "approval", "clearance", "fda", "phase",
    "bankruptcy", "chapter 11", "delisting", "split", "dividend",
    "buyback", "downgrade", "upgrade", "initiated", "price target",
    "cpi", "jobs report", "fomc", "rate cut", "rate hike", "treasury yields",
    "halts", "resumes trading", "sec filing",
]
MOVE_RE = re.compile("|".join([re.escape(k) for k in MOVE_KEYWORDS]), re.I)

BULLISH_HINTS = re.compile(r"\b(approval|beat|beats|above expectations|raises|upgrade|record|surge|positive|wins? contract|buyback|raises outlook)\b", re.I)
BEARISH_HINTS = re.compile(r"\b(downgrade|miss|misses|below expectations|cuts|recall|delay|halts?|bankrupt|chapter 11|investigation|probe|lawsuit|warning)\b", re.I)

TICKER_PATTERNS = [
    re.compile(r"\\$([A-Z]{1,5}\d?)"),
    re.compile(r"\b(?:NASDAQ|NYSE|AMEX|OTC)[\s:]+([A-Z]{1,5}\d?)\b", re.I),
    re.compile(r"/symbol/([A-Z]{1,5}\d?)\b"),
]

# =========================
#  Utility functions
# =========================
def now_et():
    return datetime.now(ET)

def in_window(ts):
    return ts.weekday() < 5 and WINDOW_START <= ts.time() <= WINDOW_END

def clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(text or "")).strip())

def extract_valid_ticker(text):
    for pattern in TICKER_PATTERNS:
        for match in pattern.finditer(text):
            t = match.group(1).upper()
            if t in VALID_TICKERS and t not in BLACKLIST:
                return t
    return None

def significant(title, summary):
    return bool(MOVE_RE.search(f"{title} {summary}".lower()))

def polarity(title, summary):
    blob = f"{title} {summary}"
    if BEARISH_HINTS.search(blob): return "bearish"
    if BULLISH_HINTS.search(blob): return "bullish"
    return "neutral"

def fmt_message(label, title, link, ticker):
    icon = "\U0001F7E9" if label == "bullish" else ("\U0001F7E5" if label == "bearish" else "\U0001F7E6")
    tstr = f" \u2014 ${ticker}" if ticker else ""
    return f"{icon} *{label.upper()}*{tstr}\n{title}\n{link}"

# =========================
#  Ticker loader
# =========================
def load_tickers(force=False):
    global LAST_SYMBOLS_LOAD, VALID_TICKERS
    if not force and LAST_SYMBOLS_LOAD and (now_et() - LAST_SYMBOLS_LOAD) < timedelta(hours=24):
        return
    tickers = set()
    for url in SYMBOLS_URLS:
        try:
            r = session.get(url, timeout=10)
            r.raise_for_status()
            for line in r.text.splitlines():
                if line and not line.startswith(("Symbol", "File")):
                    sym = line.split("|", 1)[0].strip().upper()
                    if 1 <= len(sym) <= 5:
                        tickers.add(sym)
        except Exception:
            continue
    if tickers:
        VALID_TICKERS = tickers
        LAST_SYMBOLS_LOAD = now_et()

load_tickers(force=True)

# =========================
#  Deduplication
# =========================
SEEN_FILE = "/tmp/seen_news.json"
try:
    with open(SEEN_FILE, "r") as f:
        SEEN = set(json.load(f))
except Exception:
    SEEN = set()

def seen_key(link, title):
    return hashlib.sha1(f"{link}|{title}".encode()).hexdigest()

def remember(key):
    SEEN.add(key)
    if len(SEEN) % 50 == 0:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(SEEN), f)

def flush_seen():
    with open(SEEN_FILE, "w") as f:
        json.dump(list(SEEN), f)

# =========================
#  Telegram
# =========================
def send(chat_id, text):
    try:
        resp = session.post(TG_API, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }, timeout=10)
        print("Telegram send response:", resp.status_code, resp.text)
    except Exception as e:
        print("Telegram send error:", e)

def send_brief(market_items, biotech_items):
    if market_items:
        header = "\U0001F305 *Good morning!* Here are stocks & catalysts to watch:"
        body = "\n".join([f"\u2022 {clean(title)[:120]} \u2014 ${ticker if ticker else '(no ticker)'}\n{link}" for (title, link, ticker) in market_items[:5]])
        send(TG_MARKET, f"{header}\n\n{body}")

    if biotech_items and TG_BIOTECH:
        header = "\U0001F305 *Biotech Brief:*"
        body = "\n".join([f"\u2022 {clean(title)[:120]} \u2014 ${ticker if ticker else '(no ticker)'}\n{link}" for (title, link, ticker) in biotech_items[:5]])
        send(TG_BIOTECH, f"{header}\n\n{body}")

# =========================
#  Feed Scanner
# =========================
def scan_and_send(feeds, force_bio=False):
    load_tickers()
    brief_items = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        for e in feed.entries[:12]:
            title = clean(e.get("title", ""))
            link = e.get("link", "").strip()
            if not title or not link:
                continue
            key = seen_key(link, title)
            if key in SEEN:
                continue
            summary = clean(e.get("summary", ""))
            if not significant(title, summary):
                continue
            blob = f"{title} {summary} {link}"
            ticker = extract_valid_ticker(blob)
            chat = TG_BIOTECH if force_bio and TG_BIOTECH else TG_MARKET
            label = polarity(title, summary)
            msg = fmt_message(label, title, link, ticker)
            send(chat, msg)
            remember(key)
            if len(brief_items) < 8:
                brief_items.append((title, link, ticker))
    return brief_items

# =========================
#  Main loop
# =========================
if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        print("\n\u2705 Running in TEST mode: Sending one-time Morning Brief")
        market_items = [("Test Market Headline", "https://example.com", "TEST")]
        biotech_items = [("Test Biotech Headline", "https://example.com", "BIOT")]
        print("Market items found:", market_items)
        print("Biotech items found:", biotech_items)
        send_brief(market_items, biotech_items)
        flush_seen()
        print("\n\u2705 Test brief sent")
    else:
        while True:
            now = now_et()
            if now.weekday() < 5 and now.hour == BRIEF_HOUR and BRIEF_SENT_DATE != now.date():
                market_items = scan_and_send(FEEDS_MARKET)
                biotech_items = scan_and_send(FEEDS_BIOTECH, force_bio=True)
                send_brief(market_items, biotech_items)
                BRIEF_SENT_DATE = now.date()
                flush_seen()
            if in_window(now):
                scan_and_send(FEEDS_MARKET)
                scan_and_send(FEEDS_BIOTECH, force_bio=True)
                flush_seen()
            time.sleep(60)
