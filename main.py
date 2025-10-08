<<<<<<< HEAD
import os
import time
import requests
import feedparser

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# Expanded keyword list
KEYWORDS = {
    "bullish": [
        "approval", "partnership", "merger", "acquisition", "buyout",
        "contract", "record revenue", "guidance raised", "expansion",
        "phase 3", "fda clears", "strategic alliance", "collaboration",
        "order received"
    ],
    "bearish": [
        "offering", "atm", "dilution", "bankruptcy", "reverse split",
        "guidance cut", "lawsuit", "resignation", "restatement",
        "layoffs", "delisting", "going concern"
    ]
}

# Free public RSS sources — covers large caps, small caps, and OTC
FEEDS = [
    # Large and mid caps
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL,MSFT,TSLA,AMZN,NVDA,GOOG,META,AMD,NFLX,INTC&region=US&lang=en-US",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=JPM,BAC,WFC,C,GS,MS,USB&region=US&lang=en-US",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=XOM,CVX,SHEL,NEE,BA,CAT,DE,GE&region=US&lang=en-US",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=JNJ,PFE,MRNA,BMY,AMGN,LLY,BIIB,NVO,VRTX,REGN&region=US&lang=en-US",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=WMT,TGT,COST,NKE,HD,LOW,MCD,SBUX,PG,KO&region=US&lang=en-US",
    # Example penny/small-cap list (edit or expand anytime)
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=DURU,ALPP,IQST,ENZC,BRQS,HCMC,BRTX,GTII&region=US&lang=en-US",
    # Major PR wires (hit many microcaps)
    "https://www.globenewswire.com/RssFeed/org/12199/feedTitle/GlobeNewswire%20-%20Press%20Releases",
    "https://www.prnewswire.com/rss/news-releases-list.rss",
    "https://www.businesswire.com/portal/site/home/news/",
    # Micro-cap / OTC sources
    "https://www.accesswire.com/rss/latest",
    "https://www.otcmarkets.com/rss/otc_news"
]

def send_alert(text):
    """Send a Telegram message"""
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text, "disable_web_page_preview": True})

def check_news():
    """Fetch latest headlines and look for key phrases"""
    for feed in FEEDS:
        d = feedparser.parse(feed)
        for entry in d.entries[:10]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            lowered = title.lower()
            for tag, words in KEYWORDS.items():
                if any(w in lowered for w in words):
                    icon = "🟩" if tag == "bullish" else "🟥"
                    send_alert(f"{icon} *{tag.upper()}* — {title}\n{link}")
                    break

if __name__ == "__main__":
    while True:
        check_news()
        time.sleep(300)  # check every 5 minutes
=======
# main.py
import os
import time
import re
from datetime import datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

import requests
import feedparser

# ====== Telegram config ======
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_MARKET_CHAT = os.getenv("TG_CHAT_ID")  # market/general channel (required)
TG_BIO_CHAT = os.getenv("TG_BIOTECH_CHAT_ID") or TG_MARKET_CHAT  # fallback to market if not set

if not TG_BOT_TOKEN or not TG_MARKET_CHAT:
    raise SystemExit("Missing TG_BOT_TOKEN or TG_CHAT_ID environment variables.")

API_URL = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

# ====== Scheduling ======
NY = ZoneInfo("America/New_York")
WINDOW_START, WINDOW_END = dtime(7, 0), dtime(20, 0)  # 7:00–20:00 ET

# Daily brief (9:00 AM ET) built from headlines since 7:00 AM
DAILY_BRIEF_ET_HOUR = 9
BRIEF_LOOKBACK_MIN = 120
sent_brief_on_date = None

# ====== Throttling ======
TITLE_MAX = 110
TICKER_COOLDOWN_MIN = 60
HOURLY_CAP = 5

# ====== High-impact patterns ======
BULLISH_PATTERNS = [
    r"\b(merger|acquisition|buyout|take[- ]?private)\b",
    r"\b(fda (approval|clears)|pdufa|phase\s*3|meets primary endpoint|positive topline)\b",
    r"\b(contract|award|order|license|distribution deal|commercial launch|strategic (partnership|alliance|collaboration))\b",
    r"\b(record revenue|beat|guidance (raised|increase|boost|upgraded))\b",
]
BEARISH_PATTERNS = [
    r"\b(offering|424b5|s-3|follow[- ]on|atm|dilution|convertible note)\b",
    r"\b(bankruptcy|chapter 11|going concern|delisting|nasdaq deficiency|reverse split)\b",
    r"\b(guidance (cut|reduce|lower|downgraded)|restatement|sec investigation)\b",
    r"\b(lawsuit|class action|resignation)\b",
]
RE_BULL = re.compile("|".join(BULLISH_PATTERNS), re.I)
RE_BEAR = re.compile("|".join(BEARISH_PATTERNS), re.I)

# Biotech classifier helpers
BIO_WORDS = [
    "fda", "biotech", "biopharma", "trial", "phase", "endpoint", "enrollment",
    "drug", "therapy", "oncology", "indication", "pdufa", "orphan", "breakthrough"
]
BIO_SRC_HINTS = ["biopharmadive.com", "fiercebiotech.com", "endpts.com", "statnews.com", "clinicaltrialsarena.com", "nih.gov"]

# ====== Feeds ======
FEEDS_MARKET = [
    # Large/mid caps
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL,MSFT,TSLA,AMZN,NVDA,GOOG,META,AMD,NFLX,INTC&region=US&lang=en-US",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=JPM,BAC,WFC,C,GS,MS,USB&region=US&lang=en-US",
    # Micro/small caps (edit as you like)
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=RR,DURU,ALPP,IQST,ENZC,GTII,BRTX,BRQS&region=US&lang=en-US",
    # Broad PR/IR wires (also catch non-bio items)
    "https://www.globenewswire.com/RssFeed/org/12199/feedTitle/GlobeNewswire%20-%20Press%20Releases",
    "https://www.prnewswire.com/rss/news-releases-list.rss",
    "https://www.businesswire.com/portal/site/home/news/",
    "https://www.accesswire.com/rss/latest",
    "https://www.otcmarkets.com/rss/otc_news",
]

FEEDS_BIOTECH = [
    # Core biotech news sites
    "https://www.biopharmadive.com/feeds/news/",
    "https://www.fiercebiotech.com/rss.xml",
    "https://endpts.com/feed/",
    "https://www.statnews.com/feed/",
    "https://www.clinicaltrialsarena.com/feed/",
    "https://www.nih.gov/news-events/news-releases/feed",
    # Health/biotech PR wires
    "https://www.prnewswire.com/rss/health-latest-news.rss",
    "https://www.globenewswire.com/RssFeed/org/2700/feedTitle/BioTech%20Press%20Releases",
]

# ====== State ======
seen_ids = set()
last_alert_by_ticker: dict[str, datetime] = {}
last_hour_bucket = None
alerts_in_bucket = 0

# rolling hits store for 9am brief
hits_log = []  # list of dicts: {"t": datetime, "tk": str, "impact": "BULLISH"/"BEARISH", "title": str}

# ====== Utils ======
def in_window(now_et: datetime) -> bool:
    t = now_et.time()
    return WINDOW_START <= t <= WINDOW_END

def short(txt: str, n: int = TITLE_MAX) -> str:
    txt = (txt or "").strip()
    return (txt[: n - 1] + "…") if len(txt) > n else txt

def classify_impact(title: str) -> str | None:
    if RE_BULL.search(title): return "BULLISH"
    if RE_BEAR.search(title): return "BEARISH"
    return None

def looks_biotech(title: str, link: str) -> bool:
    t = (title or "").lower()
    if any(w in t for w in BIO_WORDS):
        return True
    return any(host in (link or "").lower() for host in BIO_SRC_HINTS)

def guess_ticker(title: str) -> str | None:
    # lightweight ticker guess: 2–5 uppercase letters bounded by non-letters
    m = re.search(r"\b([A-Z]{2,5})\b(?:\s|,|:|\)|$)", title or "")
    return m.group(1) if m else None

def rate_limited(ticker: str, now_et: datetime) -> bool:
    global last_hour_bucket, alerts_in_bucket
    # Per-ticker cooldown
    last = last_alert_by_ticker.get(ticker)
    if last and (now_et - last) < timedelta(minutes=TICKER_COOLDOWN_MIN):
        return True
    # Hourly cap
    bucket = now_et.replace(minute=0, second=0, microsecond=0)
    if last_hour_bucket != bucket:
        last_hour_bucket, alerts_in_bucket = bucket, 0
    return alerts_in_bucket >= HOURLY_CAP

def send_to(chat_id: str, text: str):
    try:
        requests.post(API_URL, json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True
        }, timeout=10)
    except Exception as e:
        print("telegram send error:", e)

def record_hit(tk: str, impact: str, title: str, now_et: datetime):
    hits_log.append({"t": now_et, "tk": tk, "impact": impact, "title": title})

def prune_hits(now_et: datetime):
    cutoff = now_et - timedelta(minutes=BRIEF_LOOKBACK_MIN)
    # keep recent hits only
    i = 0
    for i, h in enumerate(hits_log):
        if h["t"] >= cutoff:
            break
    if i > 0:
        del hits_log[:i]

def build_morning_brief(now_et: datetime) -> str:
    prune_hits(now_et)
    if not hits_log:
        return "Good morning! No high-impact catalysts spotted yet. I’ll ping you as they appear."

    # score tickers by recent high-impact mentions
    scores = {}
    examples = {}
    for h in hits_log:
        tk = h["tk"]
        scores[tk] = scores.get(tk, 0) + (2 if h["impact"] == "BULLISH" else 1)
        examples.setdefault(tk, h["title"])  # keep first example

    # top 6
    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:6]
    lines = ["Good morning! These are the stocks to watch today:"]
    for tk, _ in top:
        last = next((h for h in reversed(hits_log) if h["tk"] == tk), None)
        tag = "🟩" if last and last["impact"] == "BULLISH" else "🟥"
        example = examples.get(tk, "")
        example = example[:90] + ("…" if len(example) > 90 else "")
        lines.append(f"{tag} {tk}: {example}")
    return "\n".join(lines)

# ====== Core ======
def scan_and_route(feeds: list[str], force_bio: bool = False):
    """Parse feeds, filter, and route to biotech or market channels."""
    global alerts_in_bucket
    now_et = datetime.now(NY)

    for feed in feeds:
        try:
            d = feedparser.parse(feed)
        except Exception as e:
            print("feed parse error:", feed, e)
            continue

        for e in d.entries[:20]:
            uid = e.get("id") or e.get("link") or e.get("title")
            if not uid or uid in seen_ids:
                continue
            seen_ids.add(uid)

            title = e.get("title", "") or ""
            link = e.get("link", "") or ""
            impact = classify_impact(title)
            if not impact:
                continue

            # decide route
            is_bio = force_bio or looks_biotech(title, link)
            target_chat = TG_BIO_CHAT if is_bio else TG_MARKET_CHAT
            prefix = "🧬 BIO — " if is_bio else "📊 MKT — "

            # throttling
            ticker = guess_ticker(title) or ("BIO" if is_bio else "TICKER")
            if rate_limited(ticker, now_et):
                continue

            icon = "🟩" if impact == "BULLISH" else "🟥"
            line = f"{icon} {prefix}{short(title)}\n{link}"
            send_to(target_chat, line)

            # update throttles & brief memory
            last_alert_by_ticker[ticker] = now_et
            alerts_in_bucket += 1
            record_hit(ticker, impact, title, now_et)

def main():
    global sent_brief_on_date
    while True:
        now_et = datetime.now(NY)

        # 9:00 AM ET daily brief (once per day)
        if (WINDOW_START <= now_et.time() <= WINDOW_END
            and now_et.hour == DAILY_BRIEF_ET_HOUR
            and sent_brief_on_date != now_et.date()):
            msg = build_morning_brief(now_et)
            send_to(TG_MARKET_CHAT, msg)
            sent_brief_on_date = now_et.date()

        if in_window(now_et):
            # General/market sources
            scan_and_route(FEEDS_MARKET, force_bio=False)
            # Biotech-only sources → force route to biotech channel
            scan_and_route(FEEDS_BIOTECH, force_bio=True)

        time.sleep(60)  # check once per minute within the window

if __name__ == "__main__":
    main()
>>>>>>> 8726f46 (Added biotech and morning brief features)
