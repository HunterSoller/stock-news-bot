import os, re, time, hashlib, feedparser, requests
from datetime import datetime, timedelta, time as dtime
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

# ========= ENV =========
TG_BOT_TOKEN       = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID         = os.getenv("TG_CHAT_ID")           # main channel
TG_BIOTECH_CHAT_ID = os.getenv("TG_BIOTECH_CHAT_ID")   # biotech channel
if not TG_BOT_TOKEN or not TG_CHAT_ID or not TG_BIOTECH_CHAT_ID:
    raise SystemExit("Missing env: TG_BOT_TOKEN, TG_CHAT_ID, TG_BIOTECH_CHAT_ID")

API_URL = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

# ========= TIME =========
NY                = ZoneInfo("America/New_York")
WINDOW_START      = dtime(7, 0)   # 07:00 ET
WINDOW_END        = dtime(20, 0)  # 20:00 ET
SCAN_EVERY_SEC    = 60
DAILY_BRIEF_HOUR  = 9             # 09:00 ET

# ========= LIMITS =========
DEDUP_TTL_SEC     = 120 * 60      # 2h
TICKER_COOLDOWN   = 60 * 60       # 60 min per ticker
HOURLY_CAP        = 6             # per channel/hour

# ========= FEEDS =========
FEEDS_MAIN = [
    # Yahoo / broad finance
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,QQQ,AAPL,MSFT,AMZN,NVDA,META,TSLA&region=US&lang=en-US",
    "https://www.marketwatch.com/feeds/topstories",
    "https://seekingalpha.com/market_currents.xml",
    # Wires
    "https://www.prnewswire.com/rss/finance/all-financial-services-news.rss",
    "https://www.globenewswire.com/RssFeed/industry/Financial%20Services/feedTitle/Global%20Financial%20Services",
    # CNBC (added)
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # Top News
    "https://www.cnbc.com/id/15839069/device/rss/rss.html",   # Investing
    "https://www.cnbc.com/id/15839135/device/rss/rss.html",   # Markets
]

FEEDS_BIOTECH = [
    "https://www.biopharmadive.com/feeds/news/",
    "https://www.fiercebiotech.com/rss/xml",
    "https://www.prnewswire.com/rss/health-latest-news.rss",
    "https://www.globenewswire.com/RssFeed/industry/Healthcare/feedTitle/Global%20Healthcare%20News",
    "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases",
]

# ========= RULES =========
BULLISH = {
    "beat", "beats", "tops", "exceeds", "raises", "hikes", "upgrade",
    "acquisition", "merger", "partnership", "contract", "award", "buyback",
    "approval", "clearance", "authorization", "fda approves", "phase 3 positive",
}
BEARISH = {
    "miss", "misses", "cuts", "lowered", "downgrade",
    "lawsuit", "investigation", "recall", "halts", "suspends",
    "bankruptcy", "going concern", "offering", "registered direct", "atm offering"
}
BIOTECH_HINTS = {
    "fda","trial","phase 1","phase 2","phase 3","phase i","phase ii","phase iii",
    "biotech","biologic","biosimilar","oncology","ind","nda","bla","orphan","gene","therapy","ema"
}
BOILER = ["inc","ltd","llc","corp","company","plc","press release"]
NOT_TICKER = {"AND","THE","LLC","INC","NEWS","NASDAQ","NYSE","AMEX","OTC","CEO","CFO","FDA","ETF","EPS"}

# ========= STATE =========
recent_hash = {}                    # dedupe cache: key -> expiry_ts
last_sent_by_ticker = {}            # ticker -> last_ts
hour_bucket = {"market": [], "biotech": []}  # timestamps of sends per channel
brief_sent_on_date = None
counts_market_by_date = {}          # {date: {TICKER: count}}
counts_biotech_by_date = {}         # {date: {TICKER: count}}

# ========= HELPERS =========
def now_et() -> datetime:
    return datetime.now(NY)

def in_window(ts: datetime) -> bool:
    t = ts.time()
    return WINDOW_START <= t <= WINDOW_END

def compact(title: str, maxlen: int = 120) -> str:
    t = title.strip()
    t = re.sub(r"[-–—:|]+", " ", t)
    for w in BOILER:
        t = re.sub(rf"\b{re.escape(w)}\b", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    return (t[:maxlen] + "…") if len(t) > maxlen else t

def is_biotech(title: str, link: str) -> bool:
    low = title.lower()
    if any(k in low for k in BIOTECH_HINTS): return True
    host = urlparse(link).netloc.lower()
    return any(x in host for x in ["biopharmadive","fiercebiotech","fda.gov","biospace","clinicaltrials"])

def sentiment(title: str):
    low = title.lower()
    if any(k in low for k in BEARISH): return "🟥","BEARISH"
    if any(k in low for k in BULLISH): return "🟩","BULLISH"
    return "🟦","UPDATE"

def looks_market_moving(title: str) -> bool:
    low = title.lower()
    return any(k in low for k in BULLISH | BEARISH)

def extract_ticker(title: str, link: str) -> str | None:
    # $TICKER in title
    m = re.search(r"\$([A-Z]{1,5})(?![A-Za-z])", title)
    if m: return m.group(1)
    # (NASDAQ: ABC) or NYSE: ABC
    m = re.search(r"(NASDAQ|NYSE|AMEX|OTC)[\]:\s]+([A-Z]{1,5})(?![A-Za-z])", title, re.I)
    if m: return m.group(2).upper()
    # URL symbol param or /quote/ABC
    try:
        qs = parse_qs(urlparse(link).query)
        if "symbol" in qs and qs["symbol"]:
            sym = qs["symbol"][0].upper()
            if 1 <= len(sym) <= 5 and sym.isalpha(): return sym
    except Exception:
        pass
    path = urlparse(link).path.upper()
    m = re.search(r"/(QUOTE|SYMBOL)/([A-Z]{1,5})(?:/|$)", path)
    if m: return m.group(2)
    # ALL-CAPS token fallback
    tokens = re.findall(r"\b[A-Z]{1,5}\b", title)
    for tok in tokens:
        if tok not in NOT_TICKER and tok.isalpha():
            return tok
    return None

def canonical_key(title: str, link: str) -> str:
    base = link.split("?")[0].lower()
    # normalize title: lower + remove site tags after " - " or " | "
    t = title.lower().split(" - ")[0].split(" | ")[0]
    t = re.sub(r"\s+", " ", t).strip()
    return hashlib.sha256(f"{t}|{base}".encode()).hexdigest()

def dedup(title: str, link: str) -> bool:
    # purge
    now_ts = time.time()
    for k, exp in list(recent_hash.items()):
        if exp < now_ts: del recent_hash[k]
    key = canonical_key(title, link)
    if key in recent_hash: return True
    recent_hash[key] = now_ts + DEDUP_TTL_SEC
    return False

def ticker_cooldown(ticker: str | None) -> bool:
    if not ticker: return False
    now_ts = time.time()
    last = last_sent_by_ticker.get(ticker)
    if last and (now_ts - last) < TICKER_COOLDOWN:
        return True
    last_sent_by_ticker[ticker] = now_ts
    return False

def can_send(channel_key: str) -> bool:
    # hourly cap
    cutoff = now_et() - timedelta(hours=1)
    hour_bucket[channel_key] = [t for t in hour_bucket[channel_key] if t >= cutoff]
    return len(hour_bucket[channel_key]) < HOURLY_CAP

def mark_sent(channel_key: str):
    hour_bucket[channel_key].append(now_et())

def send(chat_id: str, text: str):
    try:
        r = requests.post(API_URL, json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True
        }, timeout=15)
        if r.status_code >= 400:
            print("Telegram error:", r.status_code, r.text[:180])
    except Exception as e:
        print("Send error:", e)

def record_count(ticker: str | None, biotech: bool):
    if not ticker: return
    d = now_et().date()
    bucket = counts_biotech_by_date if biotech else counts_market_by_date
    day = bucket.setdefault(d, {})
    day[ticker] = day.get(ticker, 0) + 1

def build_brief(bucket: dict) -> str:
    d = now_et().date()
    day = bucket.get(d, {})
    if not day:
        return "☀️ Good morning!\n\nNo major tickers yet. Scanning is live."
    top = sorted(day.items(), key=lambda x: x[1], reverse=True)[:5]
    lines = [f"• ${t} — {c} hit(s)" for t, c in top]
    return "☀️ Good morning!\n\n**Tickers to watch**\n" + "\n".join(lines)

def maybe_send_briefs():
    global brief_sent_on_date
    nowd = now_et()
    if nowd.hour == DAILY_BRIEF_HOUR and (brief_sent_on_date != nowd.date()):
        send(TG_CHAT_ID, build_brief(counts_market_by_date))
        send(TG_BIOTECH_CHAT_ID, build_brief(counts_biotech_by_date))
        brief_sent_on_date = nowd.date()

# ========= CORE =========
def route_entry(entry, force_bio: bool = False):
    title = (entry.get("title") or "").strip()
    link  = (entry.get("link") or "").strip()
    if not title or not link:
        return

    # Only market-moving items
    if not looks_market_moving(title):
        return

    # Dedup by normalized title/link
    if dedup(title, link):
        return

    # Biotech or not
    biotech = force_bio or is_biotech(title, link)

    # Sentiment (UPDATEs skipped)
    icon, tag = sentiment(title)
    if tag == "UPDATE":
        return

    # Ticker extraction + cooldown
    ticker = extract_ticker(title, link)
    if ticker and ticker_cooldown(ticker):
        return

    # Message
    head = f"{icon} *{tag}*"
    if ticker:
        head += f" — ${ticker}"
    msg = f"{head}\n{compact(title)}\n{link}"

    # Hourly cap + send
    if biotech:
        if can_send("biotech"):
            send(TG_BIOTECH_CHAT_ID, msg)
            mark_sent("biotech")
            record_count(ticker, biotech=True)
        else:
            print("biotech hourly cap reached; skip")
    else:
        if can_send("market"):
            send(TG_CHAT_ID, msg)
            mark_sent("market")
            record_count(ticker, biotech=False)
        else:
            print("market hourly cap reached; skip")

def scan(feeds: list[str], force_bio: bool = False):
    for url in feeds:
        try:
            d = feedparser.parse(url)
            for e in d.entries[:10]:
                route_entry(e, force_bio=force_bio)
        except Exception as ex:
            print("Feed error:", url, str(ex)[:200])

def main():
    print("scanner live")
    while True:
        nowd = now_et()
        maybe_send_briefs()
        if in_window(nowd):
            scan(FEEDS_MAIN, force_bio=False)
            scan(FEEDS_BIOTECH, force_bio=True)
        time.sleep(SCAN_EVERY_SEC)

if __name__ == "__main__":
    main()