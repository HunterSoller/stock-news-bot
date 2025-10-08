import os
import re
import time
import html
from datetime import datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

import requests
import feedparser

# ────────────────────────────
# Telegram config (env vars)
# ────────────────────────────
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")              # Market/general
TG_BIOTECH_CHAT_ID = os.getenv("TG_BIOTECH_CHAT_ID")

if not TG_BOT_TOKEN or not TG_CHAT_ID:
    raise SystemExit("Missing TG_BOT_TOKEN or TG_CHAT_ID environment variable(s).")

API_URL = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

# ────────────────────────────
# Schedules / windows (ET)
# ────────────────────────────
ET = ZoneInfo("America/New_York")
WINDOW_START = dtime(7, 0)    # 7:00 ET
WINDOW_END   = dtime(20, 0)   # 20:00 ET
DAILY_BRIEF_ET_HOUR = 9       # 9:00 ET

# ────────────────────────────
# Feeds
# ────────────────────────────
# General/market movers (add/remove as you like)
FEEDS_MARKET = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL,MSFT,TSLA,AMZN,NVDA,AMD,META,GOOGL,PLTR&region=US&lang=en-US",
    "https://www.globenewswire.com/RssFeed/subjectcode/11-Market%20Updates/feedTitle/GlobeNewswire%20-%20Market%20Updates",
    "https://www.prnewswire.com/rss/all-news.rss",
]

# Biotech-specific
FEEDS_BIOTECH = [
    "https://www.fiercebiotech.com/rss.xml",
    "https://www.biopharmadive.com/feeds/news/",
]

# ────────────────────────────
# Keyword rules
# ────────────────────────────
KEYWORDS = {
    "bullish": [
        "approval", "approves", "fast track", "breakthrough",
        "partnership", "merger", "acquisition", "beats", "raises guidance",
        "contract", "wins contract", "record revenue", "phase 3 meets",
        "phase iii meets", "topline positive", "initiates buyback",
    ],
    "bearish": [
        "halts", "hold placed", "bankruptcy", "lawsuit",
        "guidance cut", "misses", "downgrade", "sec probe", "doj probe",
        "data miss", "partial hold", "complete response letter", "crl",
        "adverse event", "trial fails", "phase 3 fails", "delay",
    ],
}

# A small deny-list for obvious non-tickers that sometimes appear as "$MKT", "$NEWS", etc.
FAKE_TICKERS = {
    "MKT", "NEWS", "PR", "CEO", "FDA", "BIO", "AI", "ETF", "IPO", "SEC", "DOJ"
}

# Seen cache to avoid duplicates (title/link hash)
SEEN = set()

# Daily brief throttling
sent_brief_on_date = None

# ────────────────────────────
# Helpers
# ────────────────────────────
HTML_TAG_RE = re.compile(r"<[^>]+>")
TICKER_RE = re.compile(
    r"(?:\$(?P<dollar>[A-Z]{1,5})\b)|(?:\b(?:NASDAQ|NYSE|AMEX|OTC)[:\s]+(?P<xchg>[A-Z]{1,5})\b)"
)

def now_et() -> datetime:
    return datetime.now(ET)

def in_window(dt: datetime) -> bool:
    """Weekdays only, and between WINDOW_START–WINDOW_END ET."""
    if dt.weekday() >= 5:  # 5=Sat, 6=Sun
        return False
    start = datetime.combine(dt.date(), WINDOW_START, tzinfo=ET)
    end   = datetime.combine(dt.date(), WINDOW_END, tzinfo=ET)
    return start <= dt <= end

def strip_html(s: str) -> str:
    return HTML_TAG_RE.sub("", html.unescape(s or "")).strip()

def shorten(s: str, max_len: int = 140) -> str:
    s = " ".join(s.split())
    return (s[: max_len - 1] + "…") if len(s) > max_len else s

def classify(text: str) -> str | None:
    low = text.lower()
    for w in KEYWORDS["bearish"]:
        if w in low:
            return "bearish"
    for w in KEYWORDS["bullish"]:
        if w in low:
            return "bullish"
    return None

def extract_ticker(text: str) -> str | None:
    """Return a plausible ticker or None."""
    for m in TICKER_RE.finditer(text.upper()):
        t = m.group("dollar") or m.group("xchg")
        if not t:
            continue
        if len(t) > 5:
            continue
        if not t.isalpha():
            continue
        if t in FAKE_TICKERS:
            continue
        return t
    return None

def choose_channel(force_bio: bool) -> str:
    if force_bio and TG_BIOTECH_CHAT_ID:
        return TG_BIOTECH_CHAT_ID
    return TG_CHAT_ID

def send_telegram(chat_id: str, text: str):
    try:
        requests.post(
            API_URL,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
    except Exception:
        # Keep running on transient network issues
        pass

def compose_line(tag: str, title: str, link: str, ticker: str | None) -> str:
    icon = "🟥" if tag == "bearish" else "🟩"
    head = shorten(title, 160)
    if ticker:
        return f"{icon} *{tag.upper()}* — ${ticker} | {head}\n{link}"
    return f"{icon} *{tag.upper()}* | {head}\n{link}"

def scan_and_route(feeds: list[str], force_bio: bool = False):
    """Read feeds, classify, clean, and send."""
    for url in feeds:
        d = feedparser.parse(url)
        for e in d.entries[:12]:
            title = strip_html(e.get("title", ""))
            link  = e.get("link", "").strip()
            if not title or not link:
                continue

            # de-dup
            key = (title, link)
            if key in SEEN:
                continue

            tag = classify(title)
            if not tag:
                # Skip if neutral / not meaningful
                continue

            ticker = extract_ticker(f"{title} {e.get('summary','')}")
            msg = compose_line(tag, title, link, ticker)
            send_telegram(choose_channel(force_bio), msg)
            SEEN.add(key)
            # light pacing
            time.sleep(0.7)

def build_morning_brief(now_dt: datetime) -> str:
    weekday = now_dt.strftime("%a")
    return f"🌅 *Good morning!* ({weekday} {now_dt:%b %d})\nTop catalysts today will post here during market hours."

# ────────────────────────────
# Main loop
# ────────────────────────────
def main():
    global sent_brief_on_date
    while True:
        now = now_et()

        # Morning brief once/day on weekdays at ~9:00 ET
        if now.weekday() < 5 and now.hour == DAILY_BRIEF_ET_HOUR and (sent_brief_on_date != now.date()):
            send_telegram(TG_CHAT_ID, build_morning_brief(now))
            sent_brief_on_date = now.date()

        # Work only during weekday windows
        if in_window(now):
            # Market/general
            scan_and_route(FEEDS_MARKET, force_bio=False)
            # Biotech route goes to biotech channel
            scan_and_route(FEEDS_BIOTECH, force_bio=True)

        # Sleep a bit; the feeds themselves throttle effectively
        time.sleep(120)  # ~2 minutes

if __name__ == "__main__":
    main()