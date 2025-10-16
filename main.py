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

# ================ VARIABLE SECTION ================
# All filtering parameters - modify these to control news filtering behavior

# === SENTIMENT KEYWORDS ===
# Enable/disable individual sentiment keywords for fine-tuned control
BULLISH_KEYWORDS = {
    "beats": True,           # Earnings beats, revenue beats
    "tops": True,            # Tops expectations, tops estimates
    "rises": True,           # Stock rises, price rises
    "surges": True,          # Stock surges, price surges
    "jumps": True,           # Stock jumps, price jumps
    "soars": True,           # Stock soars, price soars
    "outperforms": True,     # Outperforms market/expectations
    "upgraded": True,        # Analyst upgrades, rating upgrades
    "merger": True,          # Merger announcements
    "acquisition": True,     # Acquisition announcements
    "partnership": True,     # Strategic partnerships
    "expansion": True,       # Business expansion
    "breakthrough": True,    # Technology breakthroughs
    "approval": True,        # FDA approvals, regulatory approvals
    "launch": True,          # Product launches
    "growth": True,          # Growth announcements
    "profit": True,          # Profit increases
    "revenue": True,         # Revenue growth
    "dividend": True,        # Dividend increases
    "buyback": True,         # Share buyback programs
}

BEARISH_KEYWORDS = {
    "misses": True,          # Earnings misses, revenue misses
    "falls": True,           # Stock falls, price falls
    "drops": True,           # Stock drops, price drops
    "declines": True,        # Stock declines, price declines
    "downgraded": True,      # Analyst downgrades, rating downgrades
    "warns": True,           # Company warnings, guidance warnings
    "cuts": True,            # Dividend cuts, job cuts
    "sinks": True,           # Stock sinks, price sinks
    "bankruptcy": True,      # Bankruptcy filings
    "lawsuit": True,         # Legal issues, lawsuits
    "investigation": True,   # SEC investigations, regulatory probes
    "recall": True,          # Product recalls
    "delay": True,           # Project delays, launch delays
    "loss": True,            # Losses, quarterly losses
    "layoffs": True,         # Layoff announcements
    "restructuring": True,   # Company restructuring
    "suspension": True,      # Trading suspensions
    "default": True,         # Debt defaults
    "penalty": True,         # Regulatory penalties
    "breach": True,          # Security breaches, data breaches
}

# === FILTERING TOGGLES ===
# Master switches to enable/disable different types of filtering
ENABLE_SENTIMENT_FILTERING = False      # Filter based on bullish/bearish sentiment
ENABLE_TICKER_FILTERING = False         # Require valid stock ticker in headline
ENABLE_LENGTH_FILTERING = True         # Filter based on headline length
ENABLE_TIME_FILTERING = False          # Filter based on article age (DISABLED FOR DEBUG)
ENABLE_SECTOR_FILTERING = False        # Filter based on company sector (DISABLED FOR DEBUG)
ENABLE_IMPORTANCE_FILTERING = False    # Filter based on importance score (DISABLED FOR DEBUG)
ENABLE_DUPLICATE_FILTERING = True      # Prevent duplicate articles
ENABLE_BLACKLIST_FILTERING = True      # Filter out blacklisted terms

# === LENGTH FILTERING ===
MIN_HEADLINE_LENGTH = 20               # Minimum characters in headline
MAX_HEADLINE_LENGTH = 200              # Maximum characters in headline
MIN_WORD_COUNT = 4                     # Minimum words in headline
MAX_WORD_COUNT = 30                    # Maximum words in headline

# === TIME FILTERING ===
MAX_ARTICLE_AGE_HOURS = 24             # Maximum age of articles to process (hours)
MIN_ARTICLE_AGE_MINUTES = 5            # Minimum age to avoid very recent articles (minutes)

# === IMPORTANCE SCORING ===
MIN_IMPORTANCE_SCORE = 1               # Minimum importance score to process
BULLISH_KEYWORD_WEIGHT = 2             # Points per bullish keyword found
BEARISH_KEYWORD_WEIGHT = 2             # Points per bearish keyword found
EARNINGS_KEYWORD_BONUS = 1             # Bonus points for earnings-related terms
VOLUME_KEYWORD_BONUS = 1               # Bonus points for high-volume stocks
BREAKING_NEWS_BONUS = 2                # Bonus points for breaking news indicators

# === TICKER FILTERING ===
MIN_TICKER_LENGTH = 1                  # Minimum ticker symbol length
MAX_TICKER_LENGTH = 5                  # Maximum ticker symbol length
REQUIRE_EXPLICIT_TICKER_FORMAT = False # Require $TICKER or (TICKER) format
ALLOW_CASUAL_TICKER_DETECTION = True   # Allow detection of tickers without special formatting

# === SECTOR FILTERING ===
# Enable/disable specific sectors
ENABLED_SECTORS = {
    "technology": True,                # Tech stocks (AAPL, MSFT, GOOGL, etc.)
    "healthcare": True,                # Healthcare/biotech stocks
    "finance": True,                   # Financial stocks (JPM, BAC, etc.)
    "energy": True,                    # Energy stocks (XOM, CVX, etc.)
    "consumer": True,                  # Consumer stocks (AMZN, WMT, etc.)
    "industrial": True,                # Industrial stocks
    "materials": True,                  # Materials stocks
    "utilities": True,                 # Utility stocks
    "real_estate": True,               # REITs and real estate
    "communication": True,             # Communication stocks
}

# === BLACKLIST FILTERING ===
# Terms to exclude from ticker detection and general filtering
TICKER_BLACKLIST = {
    "USD", "FOMC", "ETF", "IPO", "AI", "GDP", "CEO", "EV", "SEC", "FDA", 
    "US", "UK", "EU", "NYC", "LA", "SF", "DC", "PR", "CEO", "CFO", "CTO",
    "COVID", "COVID-19", "NASDAQ", "NYSE", "DOW", "SPY", "QQQ", "VIX"
}

# General terms to exclude from processing
GENERAL_BLACKLIST = {
    "advertisement", "sponsored", "promotion", "click here", "subscribe",
    "newsletter", "unsubscribe", "privacy policy", "terms of service"
}

# === VOLUME FILTERING ===
# Only process stocks with sufficient trading volume (requires yfinance)
ENABLE_VOLUME_FILTERING = False        # Enable volume-based filtering
MIN_AVERAGE_VOLUME = 1000000          # Minimum average daily volume
VOLUME_CHECK_PERIOD_DAYS = 30         # Days to check for average volume

# === BREAKING NEWS INDICATORS ===
BREAKING_NEWS_KEYWORDS = {
    "breaking": True,                  # Breaking news
    "urgent": True,                    # Urgent news
    "just in": True,                    # Just in news
    "developing": True,                 # Developing story
    "update": True,                    # News update
    "alert": True,                     # News alert
}

# === EARNINGS KEYWORDS ===
EARNINGS_KEYWORDS = {
    "earnings": True,                  # Earnings reports
    "guidance": True,                  # Guidance updates
    "outlook": True,                   # Outlook statements
    "forecast": True,                  # Forecasts
    "quarterly": True,                 # Quarterly results
    "annual": True,                    # Annual results
    "revenue": True,                   # Revenue reports
    "profit": True,                    # Profit reports
    "EPS": True,                       # Earnings per share
    "EBITDA": True,                    # EBITDA reports
}

# === HIGH VOLUME STOCK TICKERS ===
# Major stocks that should get priority processing
HIGH_VOLUME_TICKERS = {
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "BRK.B",
    "UNH", "JNJ", "JPM", "V", "PG", "MA", "HD", "CVX", "PFE", "ABBV",
    "BAC", "KO", "AVGO", "PEP", "TMO", "COST", "WMT", "MRK", "ABT", "ACN"
}

# === PROCESSING LIMITS ===
MAX_ARTICLES_PER_FEED = 50            # Maximum articles to process per feed
MAX_ALERTS_PER_BATCH = 10             # Maximum alerts to send per batch
MAX_MORNING_DIGEST_ITEMS = 6          # Maximum items in morning digest

# === ADVANCED FILTERING ===
ENABLE_SENTIMENT_THRESHOLD = True      # Require minimum sentiment strength
MIN_SENTIMENT_STRENGTH = 2            # Minimum sentiment keyword count
ENABLE_MIXED_SENTIMENT_FILTERING = False  # Allow mixed sentiment articles
ENABLE_NEUTRAL_SENTIMENT = False       # Allow neutral sentiment articles

# Convert keyword dictionaries to lists for backward compatibility
BULLISH = [k for k, v in BULLISH_KEYWORDS.items() if v]
BEARISH = [k for k, v in BEARISH_KEYWORDS.items() if v]
ALL_KEYWORDS = BULLISH + BEARISH

# Regex patterns
TICKER_REGEX = re.compile(r"\\$([A-Z]{1,5})|\\(([A-Z]{1,5})\\)")
BLACKLIST = TICKER_BLACKLIST

sent_global = set()
ticker_sector_cache = {}


def clean(text):
    """Clean text by removing newlines and extra whitespace"""
    return text.replace("\n", " ").strip()

def extract_ticker(title):
    """Extract stock ticker from headline with configurable filtering"""
    if not ENABLE_TICKER_FILTERING:
        return "UNKNOWN"  # Return placeholder if ticker filtering disabled
    
    # Try explicit ticker format first ($TICKER or (TICKER))
    m = TICKER_REGEX.search(title)
    if m:
        t = (m.group(1) or m.group(2)).upper()
        if (MIN_TICKER_LENGTH <= len(t) <= MAX_TICKER_LENGTH and 
            (not ENABLE_BLACKLIST_FILTERING or t not in TICKER_BLACKLIST)):
            return t
    
    # Try casual ticker detection if enabled
    if ALLOW_CASUAL_TICKER_DETECTION:
        for w in re.findall(r"\b[A-Z]{1,5}\b", title):
            if (MIN_TICKER_LENGTH <= len(w) <= MAX_TICKER_LENGTH and 
                (not ENABLE_BLACKLIST_FILTERING or w not in TICKER_BLACKLIST)):
                return w
    
    return None

def classify_sentiment(title):
    """Classify sentiment with configurable keyword sets and thresholds"""
    if not ENABLE_SENTIMENT_FILTERING:
        return "NEUTRAL"
    
    tl = title.lower()
    
    # Count enabled bullish keywords
    bullish_count = sum(tl.count(w) for w in BULLISH_KEYWORDS.keys() if BULLISH_KEYWORDS[w])
    
    # Count enabled bearish keywords  
    bearish_count = sum(tl.count(w) for w in BEARISH_KEYWORDS.keys() if BEARISH_KEYWORDS[w])
    
    # Apply sentiment threshold if enabled
    if ENABLE_SENTIMENT_THRESHOLD:
        if bullish_count < MIN_SENTIMENT_STRENGTH and bearish_count < MIN_SENTIMENT_STRENGTH:
            return "NEUTRAL"
    
    # Determine sentiment
    if bullish_count > bearish_count:
        return "BULLISH"
    elif bearish_count > bullish_count:
        return "BEARISH"
    elif ENABLE_MIXED_SENTIMENT_FILTERING and (bullish_count > 0 or bearish_count > 0):
        return "MIXED"
    elif ENABLE_NEUTRAL_SENTIMENT:
        return "NEUTRAL"
    else:
        return "NEUTRAL"

def importance_score(title, ticker=None):
    """Calculate importance score with configurable weights and bonuses"""
    if not ENABLE_IMPORTANCE_FILTERING:
        return 1  # Return minimum score if filtering disabled
    
    tl = title.lower()
    score = 0
    
    # Base sentiment scoring with configurable weights
    for w in BULLISH_KEYWORDS.keys():
        if BULLISH_KEYWORDS[w]:
            score += tl.count(w) * BULLISH_KEYWORD_WEIGHT
    
    for w in BEARISH_KEYWORDS.keys():
        if BEARISH_KEYWORDS[w]:
            score += tl.count(w) * BEARISH_KEYWORD_WEIGHT
    
    # Earnings bonus
    earnings_count = sum(tl.count(w) for w in EARNINGS_KEYWORDS.keys() if EARNINGS_KEYWORDS[w])
    if earnings_count > 0:
        score += EARNINGS_KEYWORD_BONUS
    
    # Breaking news bonus
    breaking_count = sum(tl.count(w) for w in BREAKING_NEWS_KEYWORDS.keys() if BREAKING_NEWS_KEYWORDS[w])
    if breaking_count > 0:
        score += BREAKING_NEWS_BONUS
    
    # High volume stock bonus
    if ticker and ticker in HIGH_VOLUME_TICKERS:
        score += VOLUME_KEYWORD_BONUS
    
    return max(score, MIN_IMPORTANCE_SCORE)

def filter_by_length(title):
    """Filter articles based on headline length"""
    if not ENABLE_LENGTH_FILTERING:
        return True
    
    char_count = len(title)
    word_count = len(title.split())
    
    return (MIN_HEADLINE_LENGTH <= char_count <= MAX_HEADLINE_LENGTH and
            MIN_WORD_COUNT <= word_count <= MAX_WORD_COUNT)

def filter_by_time(article_date):
    """Filter articles based on age"""
    if not ENABLE_TIME_FILTERING:
        return True
    
    if not article_date:
        return True  # If no date, allow the article
    
    now = dt.now(ET)
    
    try:
        # Try parsing with feedparser's date parsing first
        import feedparser
        parsed_date = feedparser._parse_date(article_date)
        if parsed_date:
            article_dt = dt.fromtimestamp(parsed_date, tz=ET)
        else:
            # Fallback to manual parsing
            if 'Z' in article_date:
                article_dt = dt.fromisoformat(article_date.replace('Z', '+00:00'))
            elif '+' in article_date or article_date.endswith('GMT'):
                # Handle GMT format
                article_dt = dt.strptime(article_date.replace('GMT', '').strip(), '%a, %d %b %Y %H:%M:%S')
                article_dt = article_dt.replace(tzinfo=ET)
            else:
                # Try ISO format without timezone
                article_dt = dt.fromisoformat(article_date)
                if article_dt.tzinfo is None:
                    article_dt = article_dt.replace(tzinfo=ET)
    except Exception as e:
        print(f"[DEBUG] Date parsing error for '{article_date}': {e}")
        return True  # If we can't parse the date, allow the article
    
    age_hours = (now - article_dt).total_seconds() / 3600
    age_minutes = (now - article_dt).total_seconds() / 60
    
    return (age_minutes >= MIN_ARTICLE_AGE_MINUTES and 
            age_hours <= MAX_ARTICLE_AGE_HOURS)

def filter_by_blacklist(title):
    """Filter articles containing blacklisted terms"""
    if not ENABLE_BLACKLIST_FILTERING:
        return True
    
    tl = title.lower()
    return not any(term.lower() in tl for term in GENERAL_BLACKLIST)

def filter_by_sector(ticker):
    """Filter articles based on company sector (placeholder for future implementation)"""
    if not ENABLE_SECTOR_FILTERING:
        return True
    
    # This is a placeholder - in a real implementation, you'd look up the sector
    # For now, we'll just return True to allow all sectors
    return True

def check_volume_filter(ticker):
    """Check if stock meets volume requirements (requires yfinance)"""
    if not ENABLE_VOLUME_FILTERING:
        return True
    
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{VOLUME_CHECK_PERIOD_DAYS}d")
        if hist.empty:
            return False
        
        avg_volume = hist['Volume'].mean()
        return avg_volume >= MIN_AVERAGE_VOLUME
    except:
        return True  # If we can't check volume, allow the article

def send_telegram(msg, chat_id):
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    try:
        r = session.post(TG_API, json=payload, timeout=10)
        print(f"[SENT] To {chat_id}: {msg.splitlines()[0]}")
    except Exception as e:
        print("[ERROR] Telegram send failed:", e)

def scan_feed_list(feed_list):
    """Scan RSS feeds and apply comprehensive filtering"""
    items = []
    processed_count = 0
    
    for url in feed_list:
        feed = feedparser.parse(url)
        print(f"[FEED] {url} entries: {len(feed.entries)}")
        
        feed_items_processed = 0
        for e in feed.entries:
            # Limit articles per feed
            if feed_items_processed >= MAX_ARTICLES_PER_FEED:
                break
                
            title = clean(e.get("title", ""))
            link = e.get("link", "")
            article_date = e.get("published", "")
            
            # Skip if no title
            if not title:
                continue
            
            # Check for duplicates
            key = (title, link)
            if ENABLE_DUPLICATE_FILTERING and key in sent_global:
                continue
            
            # Apply length filtering
            if not filter_by_length(title):
                continue
            
            # Apply time filtering
            if article_date and not filter_by_time(article_date):
                continue
            
            # Apply blacklist filtering
            if not filter_by_blacklist(title):
                continue
            
            # Extract ticker
            ticker = extract_ticker(title)
            if ENABLE_TICKER_FILTERING and not ticker:
                continue
            
            # Apply sector filtering
            if ticker and not filter_by_sector(ticker):
                continue
            
            # Apply volume filtering
            if ticker and not check_volume_filter(ticker):
                continue
            
            # Classify sentiment
            sentiment = classify_sentiment(title)
            if ENABLE_SENTIMENT_FILTERING and sentiment == "NEUTRAL":
                continue
            
            # Calculate importance score
            score = importance_score(title, ticker)
            if ENABLE_IMPORTANCE_FILTERING and score < MIN_IMPORTANCE_SCORE:
                continue
            
            # Add to results
            items.append((score, sentiment, title, ticker, link))
            processed_count += 1
            feed_items_processed += 1
            
            # Limit total alerts per batch
            if processed_count >= MAX_ALERTS_PER_BATCH:
                break
    
    print(f"[FILTER] Processed {processed_count} articles from {len(feed_list)} feeds")
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
    """Send morning digest with configurable number of items"""
    all_items = scan_feed_list(FEEDS_MARKET + FEEDS_BIOTECH)
    all_items.sort(key=lambda x: x[0], reverse=True)
    top_items = all_items[:MAX_MORNING_DIGEST_ITEMS]

    if not top_items:
        print("[MORNING] No items found for digest")
        return
    
    print(f"[MORNING] Sending digest with {len(top_items)} items")
    message = f"🌅 *Good Morning!* Here are {len(top_items)} stocks to watch today:\n\n"
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
