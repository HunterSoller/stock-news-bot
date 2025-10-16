#!/usr/bin/env python3
"""
Advanced Stock News Bot with ChatGPT Integration
Scans news feeds every minute, uses ChatGPT for sentiment analysis,
and sends top trading events to Telegram every 5 minutes.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import time
import json
import re
import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import threading
from collections import deque
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import sys
import logging  # [CHANGE] Add logging
from pathlib import Path  # [CHANGE] For file paths
import yfinance as yf  # [CHANGE] For ticker validation

# ================ CONFIGURATION ================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "").strip()

if not OPENAI_API_KEY:
    raise SystemExit("Missing OPENAI_API_KEY environment variable.")
if not TG_BOT_TOKEN or not TG_CHAT_ID:
    raise SystemExit("Missing Telegram configuration.")

# News feeds to monitor
NEWS_FEEDS = [
    "https://www.cnbc.com/id/15839135/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.investing.com/rss/news.rss",
    "https://www.fiercebiotech.com/rss.xml",
    "https://www.biospace.com/rss",
]

# Bot settings
SCAN_INTERVAL_SECONDS = 60  # Scan every minute
REPORT_INTERVAL_SECONDS = 300  # Report every 5 minutes
EVENT_RETENTION_MINUTES = 5  # Keep events for 5 minutes
MAX_EVENTS_PER_SCAN = 20  # Maximum events to process per scan
MAX_EVENTS_TO_STORE = 100  # Maximum events to keep in memory

# Sleep mode settings
SLEEP_MODE_ENABLED = True  # Enable sleep mode functionality
SLEEP_START_HOUR = 21  # 9 PM
SLEEP_END_HOUR = 7    # 7 AM
SLEEP_WEEKENDS = True  # Sleep all day on weekends

# API endpoints
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
TG_API_URL = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"

# [CHANGE] Paths and logging setup
BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
CURRENT_LOG_FILE = LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"

EVENTS_JSON_PATH = BASE_DIR / "events.json"
STATE_JSON_PATH = BASE_DIR / "state.json"
SENT_HEADLINES_JSON_PATH = BASE_DIR / "sent_headlines.json"  # [CHANGE] persist sent headlines

# [CHANGE] Configure logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(CURRENT_LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

# ================ DATA STRUCTURES ================

@dataclass
class NewsEvent:
    """Represents a news event with trading relevance"""
    headline: str
    ticker: str
    article_content: str  # Full article text
    importance_reasons: List[str]
    sentiment: str  # BULLISH, BEARISH, or NEUTRAL
    confidence_score: float  # 0.0 to 1.0
    timestamp: datetime
    source_url: str
    source_feed: str
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'headline': self.headline,
            'ticker': self.ticker,
            'article_content': self.article_content,
            'importance_reasons': self.importance_reasons,
            'sentiment': self.sentiment,
            'confidence_score': self.confidence_score,
            'timestamp': self.timestamp.isoformat(),
            'source_url': self.source_url,
            'source_feed': self.source_feed
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create NewsEvent from dictionary"""
        return cls(
            headline=data['headline'],
            ticker=data['ticker'],
            article_content=data['article_content'],
            importance_reasons=data['importance_reasons'],
            sentiment=data['sentiment'],
            confidence_score=data['confidence_score'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            source_url=data['source_url'],
            source_feed=data['source_feed']
        )

# ================ GLOBAL STATE ================
news_events: deque = deque(maxlen=MAX_EVENTS_TO_STORE)
processed_articles: set = set()  # Track processed articles to avoid duplicates
session = requests.Session()
sent_headlines_sent: set = set()  # [CHANGE] Track headlines sent to avoid duplicates
valid_tickers_cache: Dict[str, bool] = {}  # [CHANGE] Cache for ticker validation

# Bot mode tracking
current_mode = "NORMAL"  # "NORMAL" or "SLEEP"
last_mode_switch = datetime.now()
sleep_events_collected = 0  # Track events collected during sleep mode
last_wake_up_time: Optional[datetime] = None  # [CHANGE] Persisted last wake-up time

# ================ PERSISTENCE HELPERS ================

def load_state():
    """[CHANGE] Load persisted state including last wake-up time"""
    global last_wake_up_time
    try:
        if STATE_JSON_PATH.exists():
            with open(STATE_JSON_PATH, 'r') as f:
                data = json.load(f)
                last = data.get('last_wake_up_time')
                if last:
                    last_wake_up_time = datetime.fromisoformat(last)
                logging.info(f"[STATE] Loaded state with last_wake_up_time={last_wake_up_time}")
        else:
            logging.info("[STATE] No state file found; will initialize on first wake-up")
    except Exception as e:
        logging.error(f"[STATE] Failed to load state: {e}")

def save_state():
    """[CHANGE] Save persisted state including last wake-up time"""
    try:
        data = {
            'last_wake_up_time': last_wake_up_time.isoformat() if last_wake_up_time else None
        }
        with open(STATE_JSON_PATH, 'w') as f:
            json.dump(data, f)
        logging.info("[STATE] State saved")
    except Exception as e:
        logging.error(f"[STATE] Failed to save state: {e}")

def load_sent_headlines():
    """[CHANGE] Load headlines that have already been sent to avoid duplicates across restarts"""
    try:
        if SENT_HEADLINES_JSON_PATH.exists():
            with open(SENT_HEADLINES_JSON_PATH, 'r') as f:
                items = json.load(f)
            for h in items:
                sent_headlines_sent.add(h)
            logging.info(f"[PERSIST] Loaded {len(sent_headlines_sent)} sent headlines")
    except Exception as e:
        logging.error(f"[PERSIST] Failed to load sent headlines: {e}")

def save_sent_headlines():
    """[CHANGE] Persist sent headlines"""
    try:
        with open(SENT_HEADLINES_JSON_PATH, 'w') as f:
            json.dump(list(sent_headlines_sent), f)
        logging.info(f"[PERSIST] Saved {len(sent_headlines_sent)} sent headlines")
    except Exception as e:
        logging.error(f"[PERSIST] Failed to save sent headlines: {e}")

def load_events_from_disk():
    """[CHANGE] Load persisted events into memory on startup"""
    try:
        if EVENTS_JSON_PATH.exists():
            with open(EVENTS_JSON_PATH, 'r') as f:
                raw = json.load(f)
                events_list = [NewsEvent.from_dict(e) for e in raw]
            for ev in events_list[-MAX_EVENTS_TO_STORE:]:
                news_events.append(ev)
            logging.info(f"[PERSIST] Loaded {len(events_list)} events from disk; {len(news_events)} in deque")
        else:
            logging.info("[PERSIST] No events file found; starting fresh")
    except Exception as e:
        logging.error(f"[PERSIST] Failed to load events: {e}")

def save_events_to_disk():
    """[CHANGE] Persist all events currently in memory to disk"""
    try:
        with open(EVENTS_JSON_PATH, 'w') as f:
            json.dump([e.to_dict() for e in list(news_events)], f)
        logging.info(f"[PERSIST] Saved {len(news_events)} events to disk")
    except Exception as e:
        logging.error(f"[PERSIST] Failed to save events: {e}")

# ================ UTILITY FUNCTIONS ================

def clean_text(text: str) -> str:
    """Clean text by removing newlines and extra whitespace"""
    return text.replace("\n", " ").strip()

def is_sleep_time() -> bool:
    """Check if current time is sleep time"""
    if not SLEEP_MODE_ENABLED:
        return False
    
    now = datetime.now()
    current_hour = now.hour
    current_weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    # Check if it's weekend and weekend sleep is enabled
    if SLEEP_WEEKENDS and current_weekday >= 5:  # Saturday (5) or Sunday (6)
        return True
    
    # Check weekday sleep hours (9 PM to 7 AM)
    if current_weekday < 5:  # Monday to Friday
        if SLEEP_START_HOUR <= SLEEP_END_HOUR:  # Same day (e.g., 9 PM to 11 PM)
            return SLEEP_START_HOUR <= current_hour < SLEEP_END_HOUR
        else:  # Overnight (e.g., 9 PM to 7 AM)
            return current_hour >= SLEEP_START_HOUR or current_hour < SLEEP_END_HOUR
    
    return False

def get_bot_mode() -> str:
    """Get current bot mode based on time"""
    return "SLEEP" if is_sleep_time() else "NORMAL"

def check_mode_switch():
    """Check if bot mode has changed and handle the switch"""
    global current_mode, last_mode_switch, sleep_events_collected
    
    new_mode = get_bot_mode()
    
    if new_mode != current_mode:
        old_mode = current_mode
        current_mode = new_mode
        last_mode_switch = datetime.now()
        
        print(f"\n🔄 [MODE_SWITCH] Switching from {old_mode} to {current_mode} mode")
        logging.info(f"[MODE_SWITCH] {old_mode} -> {current_mode}")  # [CHANGE] log mode switch
        
        if old_mode == "SLEEP" and new_mode == "NORMAL":
            # Waking up - send wake-up report
            print(f"🌅 [WAKE_UP] Bot waking up! Collected {sleep_events_collected} events during sleep")
            logging.info(f"[WAKE_UP] Waking up with {sleep_events_collected} events collected")  # [CHANGE]
            send_wake_up_report()
            sleep_events_collected = 0
        elif old_mode == "NORMAL" and new_mode == "SLEEP":
            # Going to sleep
            print(f"😴 [SLEEP] Bot going to sleep mode - will collect events but not send messages")
            logging.info("[SLEEP] Entering sleep mode")  # [CHANGE]
            sleep_events_collected = 0
        
        print(f"[MODE] Current mode: {current_mode}")
        return True
    
    return False

def fetch_article_content(url: str, retries: int = 2) -> Optional[str]:
    """Fetch and extract article content from URL with retry logic"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    for attempt in range(retries):
        try:
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 401:
                print(f"[SKIP] Article requires authentication: {url}")
                return None
            elif response.status_code == 403:
                print(f"[SKIP] Article access forbidden: {url}")
                return None
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()
            
            # Try to find article content using common selectors
            article_selectors = [
                'article',
                '.article-content',
                '.article-body',
                '.story-body',
                '.content',
                '.post-content',
                '.entry-content',
                '.article-text',
                '.story-content',
                '[data-module="ArticleBody"]',
                '.ArticleBody-articleBody',
                '.ArticleBody-articleBodyInner'
            ]
            
            article_content = None
            for selector in article_selectors:
                elements = soup.select(selector)
                if elements:
                    article_content = elements[0]
                    break
            
            # If no specific article container found, try to get main content
            if not article_content:
                main_content = soup.find('main') or soup.find('div', class_=re.compile(r'main|content|article'))
                if main_content:
                    article_content = main_content
            
            # If still no content, get body text
            if not article_content:
                article_content = soup.find('body')
            
            if article_content:
                # Extract text and clean it
                text = article_content.get_text()
                # Clean up the text
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                
                # Limit article length to avoid token limits
                if len(text) > 4000:
                    text = text[:4000] + "..."
                
                return text
            
            return None
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [401, 403]:
                print(f"[SKIP] Article access denied: {url}")
                return None
            elif attempt < retries - 1:
                print(f"[RETRY] HTTP error {e.response.status_code}, retrying...")
                time.sleep(1)
                continue
            else:
                print(f"[ERROR] Failed to fetch article after {retries} attempts: {e}")
                return None
        except Exception as e:
            if attempt < retries - 1:
                print(f"[RETRY] Error fetching article, retrying...: {e}")
                time.sleep(1)
                continue
            else:
                print(f"[ERROR] Failed to fetch article content from {url}: {e}")
                return None
    
    return None

def extract_ticker_from_headline(headline: str) -> Optional[str]:
    """Extract stock ticker from headline"""
    # Common ticker patterns
    patterns = [
        r'\$([A-Z]{1,5})\b',  # $AAPL format
        r'\(([A-Z]{1,5})\)',  # (AAPL) format
        r'\b([A-Z]{1,5})\b',  # AAPL format (less reliable)
    ]
    
    # Blacklist common false positives
    blacklist = {
        'USD', 'FOMC', 'ETF', 'IPO', 'AI', 'GDP', 'CEO', 'EV', 'SEC', 'FDA',
        'US', 'UK', 'EU', 'NYC', 'LA', 'SF', 'DC', 'PR', 'CFO', 'CTO',
        'COVID', 'NASDAQ', 'NYSE', 'DOW', 'SPY', 'QQQ', 'VIX', 'NEWS'
    }
    
    for pattern in patterns:
        matches = re.findall(pattern, headline)
        for match in matches:
            ticker = match.upper()
            if ticker not in blacklist and len(ticker) >= 1 and len(ticker) <= 5:
                return ticker
    
    return None

def call_chatgpt_api(prompt: str, max_tokens: int = 500, retries: int = 3) -> Optional[str]:
    """Call ChatGPT API with error handling and retry logic"""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a financial news analyst specializing in stock market sentiment analysis."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3
    }
    
    for attempt in range(retries):
        try:
            response = session.post(OPENAI_API_URL, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 429:  # Rate limit
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"[RATE_LIMIT] Waiting {wait_time}s before retry {attempt + 1}/{retries}")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content'].strip()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                wait_time = 2 ** attempt
                print(f"[RATE_LIMIT] HTTP 429, waiting {wait_time}s before retry {attempt + 1}/{retries}")
                time.sleep(wait_time)
                continue
            else:
                print(f"[ERROR] ChatGPT API HTTP error: {e}")
                break
        except Exception as e:
            print(f"[ERROR] ChatGPT API call failed (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(1)  # Brief delay before retry
    
    return None

# ================ TICKER VALIDATION ================

def validate_ticker(ticker: str) -> bool:
    """[CHANGE] Return True only if ticker is a real, tradable U.S. stock
    Uses yfinance to check quoteType == 'EQUITY' and presence of symbol/name.
    Caches results in valid_tickers_cache to avoid repeated lookups.
    """
    if not ticker:
        return False
    if ticker in valid_tickers_cache:
        return valid_tickers_cache[ticker]
    try:
        yf_tkr = yf.Ticker(ticker)
        info = yf_tkr.info or {}
        quote_type = info.get('quoteType') or info.get('quote_type')
        symbol = info.get('symbol') or ticker
        short_name = info.get('shortName') or info.get('longName')
        # Exclude ETFs/indices by quoteType and missing names
        is_equity = (quote_type == 'EQUITY')
        is_valid = bool(symbol) and bool(short_name) and is_equity
        valid_tickers_cache[ticker] = is_valid
        if not is_valid:
            logging.info(f"[VALIDATE] Rejected ticker: {ticker} (quoteType={quote_type}, name={short_name})")
        return is_valid
    except Exception as e:
        logging.info(f"[VALIDATE] Exception validating {ticker}: {e}")
        valid_tickers_cache[ticker] = False
        return False

def analyze_news_with_chatgpt(headline: str, ticker: str, article_content: str) -> Dict[str, any]:
    """Use ChatGPT to analyze news sentiment and importance using full article content"""
    
    # Truncate article content if too long to avoid token limits
    if len(article_content) > 3000:
        article_content = article_content[:3000] + "..."
    
    prompt = f"""
Analyze this stock news article for trading relevance:

Headline: "{headline}"
Stock Ticker: {ticker}

Full Article Content:
{article_content}

Please provide:
1. Sentiment: BULLISH, BEARISH, or NEUTRAL
2. Confidence Score: 0.0 to 1.0 (how confident you are in the sentiment)
3. Importance Reasons: List 2-4 specific reasons why this news is important for traders

Format your response as JSON:
{{
    "sentiment": "BULLISH/BEARISH/NEUTRAL",
    "confidence_score": 0.0-1.0,
    "importance_reasons": ["reason1", "reason2", "reason3"]
}}

Focus on:
- Earnings impact and financial performance
- Regulatory changes and approvals
- Market-moving events and catalysts
- Competitive advantages/threats
- Strategic announcements (mergers, partnerships, etc.)
- Product launches or delays
- Management changes
- Industry trends affecting the company
- Analyst upgrades/downgrades mentioned
- Revenue/profit guidance changes

Consider the full context of the article, not just the headline. Look for specific details, numbers, quotes, and implications that affect the stock's trading prospects.
"""
    
    response = call_chatgpt_api(prompt)
    if not response:
        return {
            "sentiment": "NEUTRAL",
            "confidence_score": 0.0,
            "importance_reasons": ["Unable to analyze"]
        }
    
    try:
        # Try to extract JSON from response
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_str = response[json_start:json_end]
            result = json.loads(json_str)
            
            # Validate and clean the response
            sentiment = result.get('sentiment', 'NEUTRAL').upper()
            if sentiment not in ['BULLISH', 'BEARISH', 'NEUTRAL']:
                sentiment = 'NEUTRAL'
            
            confidence = float(result.get('confidence_score', 0.0))
            confidence = max(0.0, min(1.0, confidence))  # Clamp to 0-1
            
            reasons = result.get('importance_reasons', ['Unable to analyze'])
            if not isinstance(reasons, list):
                reasons = [str(reasons)]
            
            return {
                "sentiment": sentiment,
                "confidence_score": confidence,
                "importance_reasons": reasons
            }
    
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"[ERROR] Failed to parse ChatGPT response: {e}")
        print(f"[DEBUG] Response was: {response}")
    
    # Fallback response
    return {
        "sentiment": "NEUTRAL",
        "confidence_score": 0.0,
        "importance_reasons": ["Analysis failed"]
    }

def select_top_events_with_chatgpt(events: List[NewsEvent]) -> List[NewsEvent]:
    """Use ChatGPT to select the top 5 most promising trading events"""
    
    if len(events) <= 5:
        return events
    
    # Prepare event summaries for ChatGPT
    event_summaries = []
    for i, event in enumerate(events):
        # Truncate article content for summary
        content_preview = event.article_content[:200] + "..." if len(event.article_content) > 200 else event.article_content
        
        summary = f"""
Event {i+1}:
- Headline: {event.headline}
- Ticker: {event.ticker}
- Sentiment: {event.sentiment}
- Confidence: {event.confidence_score:.2f}
- Reasons: {', '.join(event.importance_reasons)}
- Content Preview: {content_preview}
"""
        event_summaries.append(summary)
    
    prompt = f"""
You are a professional trader selecting the most promising stock news events for trading opportunities.

Here are {len(events)} recent news events:

{chr(10).join(event_summaries)}

Select the TOP 5 most promising events for trading based on:
1. High confidence sentiment (bullish or bearish)
2. Significant market impact potential
3. Clear trading implications
4. Recent timing relevance

Respond with ONLY the event numbers (1-{len(events)}) separated by commas, in order of priority.
Example: 3,7,1,12,5

Focus on events that provide clear trading signals - either strong bullish or bearish sentiment with high confidence.
"""
    
    response = call_chatgpt_api(prompt, max_tokens=100)
    if not response:
        # Fallback: return top 5 by confidence score
        return sorted(events, key=lambda x: x.confidence_score, reverse=True)[:5]
    
    try:
        # Parse the response to get event indices
        selected_indices = []
        for num_str in response.split(','):
            num_str = num_str.strip()
            if num_str.isdigit():
                idx = int(num_str) - 1  # Convert to 0-based index
                if 0 <= idx < len(events):
                    selected_indices.append(idx)
        
        # Return selected events, limited to 5
        selected_events = [events[i] for i in selected_indices[:5]]
        
        if len(selected_events) < 5:
            # Fill remaining slots with highest confidence events not already selected
            remaining_events = [events[i] for i in range(len(events)) if i not in selected_indices]
            remaining_events.sort(key=lambda x: x.confidence_score, reverse=True)
            selected_events.extend(remaining_events[:5-len(selected_events)])
        
        return selected_events
    
    except Exception as e:
        print(f"[ERROR] Failed to parse ChatGPT selection: {e}")
        # Fallback: return top 5 by confidence score
        return sorted(events, key=lambda x: x.confidence_score, reverse=True)[:5]

def validate_telegram_config():
    """Validate Telegram configuration"""
    if not TG_BOT_TOKEN:
        print("[ERROR] TG_BOT_TOKEN is not set in environment variables")
        return False
    if not TG_CHAT_ID:
        print("[ERROR] TG_CHAT_ID is not set in environment variables")
        return False
    
    # Check if token looks valid (should be numeric:token format)
    if ':' not in TG_BOT_TOKEN:
        print("[ERROR] TG_BOT_TOKEN format appears invalid (should be 'bot_id:token')")
        return False
    
    print(f"[CONFIG] Bot Token: {TG_BOT_TOKEN[:10]}...{TG_BOT_TOKEN[-10:]}")
    print(f"[CONFIG] Chat ID: {TG_CHAT_ID}")
    return True

def send_telegram_message(message: str, retries: int = 3) -> bool:
    """Send message to Telegram with retry logic [CHANGE]"""
    if not validate_telegram_config():
        return False
        
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    for attempt in range(retries):
        try:
            logging.info(f"[TELEGRAM] Sending message (attempt {attempt+1}/{retries})")
            response = session.post(TG_API_URL, json=payload, timeout=15)
            if response.status_code in (400, 401):
                logging.error(f"[TELEGRAM] {response.status_code} error: {response.text}")
                return False
            response.raise_for_status()
            logging.info("[TELEGRAM] Message sent successfully")
            return True
        except Exception as e:
            logging.error(f"[TELEGRAM] Send failed: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return False

# ================ MAIN FUNCTIONS ================

def scan_news_feeds() -> List[NewsEvent]:
    """Scan all news feeds and return new events"""
    new_events = []
    
    for feed_url in NEWS_FEEDS:
        try:
            print(f"[SCAN] Processing feed: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:MAX_EVENTS_PER_SCAN]:
                headline = clean_text(entry.get('title', ''))
                link = entry.get('link', '')
                
                if not headline or not link:
                    continue
                
                # Skip if already processed
                article_key = (headline, link)
                if article_key in processed_articles:
                    continue
                
                # Extract ticker
                ticker = extract_ticker_from_headline(headline)
                if not ticker:
                    continue  # Skip articles without clear ticker
                # [CHANGE] Validate ticker is a real US equity (cached)
                if not validate_ticker(ticker):
                    logging.info(f"[VALIDATE] Skipping invalid ticker: {ticker} ({headline[:50]}...)")
                    continue
                
                # Fetch full article content
                print(f"[FETCH] Getting article content: {headline[:50]}...")
                article_content = fetch_article_content(link)
                if not article_content:
                    print(f"[FALLBACK] Using headline only for: {headline[:50]}...")
                    article_content = headline  # Fallback to headline analysis
                
                # Analyze with ChatGPT using full article
                print(f"[ANALYZE] Processing: {headline[:50]}...")
                analysis = analyze_news_with_chatgpt(headline, ticker, article_content)
                
                # Create news event
                event = NewsEvent(
                    headline=headline,
                    ticker=ticker,
                    article_content=article_content,
                    importance_reasons=analysis['importance_reasons'],
                    sentiment=analysis['sentiment'],
                    confidence_score=analysis['confidence_score'],
                    timestamp=datetime.now(),
                    source_url=link,
                    source_feed=feed_url
                )
                
                new_events.append(event)
                processed_articles.add(article_key)
                
                # Delay to avoid rate limiting
                time.sleep(2)  # Increased delay for API calls
        
        except Exception as e:
            print(f"[ERROR] Failed to process feed {feed_url}: {e}")
    
    print(f"[SCAN] Found {len(new_events)} new events")
    return new_events

def cleanup_old_events():
    """Remove events older than retention period"""
    # [CHANGE] Preserve overnight events: skip cleanup during sleep and before 7 AM
    now = datetime.now()
    if is_sleep_time() or now.hour < 7:
        logging.info("[CLEANUP] Skipped during sleep/overnight to preserve events")
        return

    cutoff_time = now - timedelta(minutes=EVENT_RETENTION_MINUTES)

    removed_count = 0
    while news_events and news_events[0].timestamp < cutoff_time:
        news_events.popleft()
        removed_count += 1

    if removed_count > 0:
        print(f"[CLEANUP] Removed {removed_count} old events, kept {len(news_events)} events within retention period")
    else:
        print(f"[CLEANUP] Kept {len(news_events)} events within retention period")

def view_current_events():
    """Display current events in the list"""
    if not news_events:
        print("[VIEW] No events currently in the list")
        return
    
    mode_indicator = "😴 SLEEP MODE" if current_mode == "SLEEP" else "📈 NORMAL MODE"
    print(f"\n[VIEW] Current Events ({len(news_events)} total) - {mode_indicator}:")
    print("=" * 80)
    
    for i, event in enumerate(news_events, 1):
        sentiment_emoji = "🟢" if event.sentiment == "BULLISH" else "🔴" if event.sentiment == "BEARISH" else "⚪"
        age_minutes = (datetime.now() - event.timestamp).total_seconds() / 60
        
        print(f"{i}. {sentiment_emoji} {event.sentiment} ${event.ticker}")
        print(f"   Headline: {event.headline}")
        print(f"   Confidence: {event.confidence_score:.1%}")
        print(f"   Reasons: {', '.join(event.importance_reasons)}")
        print(f"   Age: {age_minutes:.1f} minutes ago")
        print(f"   Source: {event.source_feed}")
        print("-" * 80)

def send_wake_up_report():
    """[CHANGE] Send Good Morning report at wake-up with top 5 bullish/bearish since last wake-up"""
    global last_wake_up_time
    if not news_events:
        print("[WAKE_UP] No events to report")
        logging.info("[WAKE_UP] No events to report")
        return

    now = datetime.now()
    since_time = last_wake_up_time or (now - timedelta(hours=12))  # default to last 12h if unknown

    # Consider only bullish/bearish events since last wake-up
    recent = [e for e in list(news_events) if e.timestamp >= since_time and e.sentiment in ("BULLISH", "BEARISH") and validate_ticker(e.ticker)]  # [CHANGE] ensure tradable tickers
    if not recent:
        print("[WAKE_UP] No bullish/bearish events since last wake-up")
        logging.info("[WAKE_UP] No bullish/bearish events since last wake-up")
        last_wake_up_time = now
        save_state()
        return

    # Top 5 by confidence
    top_events = sorted(recent, key=lambda x: x.confidence_score, reverse=True)[:5]

    # Format message per spec
    message = "🌅 Good Morning! Top Overnight Stock Events:\n"
    for i, event in enumerate(top_events, 1):
        sentiment_emoji = "🟢" if event.sentiment == "BULLISH" else "🔴"
        message += f"{i}. {sentiment_emoji} {event.sentiment} ${event.ticker} — {event.headline}\n"
        message += f"   Confidence: {event.confidence_score:.0%}\n"
        message += f"   Reasons: {', '.join(event.importance_reasons)}\n"
        message += f"   [Source]({event.source_url})\n"

    message += f"_Generated at {now.strftime('%H:%M')}_"

    if send_telegram_message(message):
        logging.info(f"[WAKE_UP] Sent morning report with {len(top_events)} events")
        # Reset overnight collection marker
        last_wake_up_time = now
        save_state()
    else:
        logging.error("[WAKE_UP] Failed to send morning report")

def send_trading_report():
    """[CHANGE] Send top 5 bullish/bearish events by confidence; avoid duplicate headlines"""
    if not news_events:
        print("[REPORT] No events to report")
        return

    # Filter for bullish/bearish, valid tickers, and exclude previously sent headlines [CHANGE]
    eligible = [
        e for e in list(news_events)
        if e.sentiment in ("BULLISH", "BEARISH")
        and validate_ticker(e.ticker)
        and e.headline not in sent_headlines_sent
    ]
    if not eligible:
        logging.info("[REPORT] No eligible new events to send")
        return

    top_events = sorted(eligible, key=lambda x: x.confidence_score, reverse=True)[:5]
    if not top_events:
        logging.info("[REPORT] No events selected for report")
        return

    message = f"📈 *Trading Alert - Top {len(top_events)} Events*\n\n"
    for i, event in enumerate(top_events, 1):
        sentiment_emoji = "🟢" if event.sentiment == "BULLISH" else "🔴"
        message += f"{i}. {sentiment_emoji} *{event.sentiment}* ${event.ticker}\n"
        message += f"   {event.headline}\n"
        message += f"   Confidence: {event.confidence_score:.1%}\n"
        message += f"   Reasons: {', '.join(event.importance_reasons)}\n"
        message += f"   [Source]({event.source_url})\n\n"

    message += f"_Report generated at {datetime.now().strftime('%H:%M:%S')}_"

    if send_telegram_message(message):
        logging.info(f"[REPORT] Sent {len(top_events)} events to Telegram")
        for ev in top_events:
            sent_headlines_sent.add(ev.headline)
        save_sent_headlines()  # [CHANGE] persist dedupe state
    else:
        logging.error("[REPORT] Failed to send report to Telegram")

def check_for_commands():
    """Check for user commands (simplified approach)"""
    # For now, we'll handle commands through a separate thread
    # This is a placeholder - in practice, you can type commands in the terminal
    pass

def main_loop():
    """Main bot loop"""
    global sleep_events_collected
    
    print("[BOOT] Advanced Stock News Bot starting...")
    print(f"[CONFIG] Scan interval: {SCAN_INTERVAL_SECONDS}s")
    print(f"[CONFIG] Report interval: {REPORT_INTERVAL_SECONDS}s")
    print(f"[CONFIG] Event retention: {EVENT_RETENTION_MINUTES} minutes")
    print(f"[CONFIG] Sleep mode: {'ENABLED' if SLEEP_MODE_ENABLED else 'DISABLED'}")
    if SLEEP_MODE_ENABLED:
        print(f"[CONFIG] Sleep hours: {SLEEP_START_HOUR}:00 - {SLEEP_END_HOUR}:00 (weekdays)")
        print(f"[CONFIG] Weekend sleep: {'ENABLED' if SLEEP_WEEKENDS else 'DISABLED'}")
    
    print("\n[COMMANDS] Available commands:")
    print("  'view' - View current events")
    print("  'report' - Send manual report to Telegram")
    print("  'quit' - Stop the bot")
    print("  Press Enter to continue normal operation\n")
    
    last_report_time = datetime.now()
    last_wakeup_triggered_date = None  # [CHANGE] Track daily 7AM trigger
    
    # [CHANGE] Load persisted state and events on startup
    load_state()
    load_events_from_disk()
    load_sent_headlines()  # [CHANGE] load sent headlines for dedupe across restarts
    
    # Initialize mode
    check_mode_switch()
    
    while True:
        try:
            current_time = datetime.now()
            
            # Check for mode switch
            mode_changed = check_mode_switch()
            
            # Check for user commands (simplified - just continue)
            # Use Ctrl+C to trigger manual report, or run command_handler.py separately
            
            # Scan for new events
            mode_indicator = "😴" if current_mode == "SLEEP" else "📈"
            print(f"[SCAN] {mode_indicator} Starting news scan at {current_time.strftime('%H:%M:%S')} ({current_mode} mode)")
            new_events = scan_news_feeds()
            
            # Add new events to storage
            for event in new_events:
                news_events.append(event)
                if current_mode == "SLEEP":
                    sleep_events_collected += 1
                # [CHANGE] Persist after each addition
                save_events_to_disk()
            
            # Cleanup old events
            cleanup_old_events()
            
            # Only send 5-min trading reports in NORMAL mode
            if current_mode == "NORMAL":
                # Check if it's time to send report
                time_since_last_report = (current_time - last_report_time).total_seconds()
                if time_since_last_report >= REPORT_INTERVAL_SECONDS:
                    print(f"[REPORT] Sending trading report...")
                    send_trading_report()
                    last_report_time = current_time
            else:
                print(f"[SLEEP] Collecting events (no reports sent) - {sleep_events_collected} events collected")
            
            # [CHANGE] Auto-trigger Good Morning report at ~7:00 local time regardless of mode (robust to loop drift)
            if current_time.hour == 7 and current_time.minute in (0, 1):
                if last_wakeup_triggered_date != current_time.date():
                    logging.info("[WAKE_UP] 7:00 AM trigger - sending morning report")
                    send_wake_up_report()
                    last_wakeup_triggered_date = current_time.date()

            print(f"[STATUS] Total events: {len(news_events)}, Mode: {current_mode}, Next scan in {SCAN_INTERVAL_SECONDS}s")
            
            # Wait for next scan
            time.sleep(SCAN_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            print("\n[INTERRUPT] Bot interrupted by user")
            print("\n[OPTIONS] What would you like to do?")
            print("1. View current events")
            print("2. Send manual report")
            print("3. Continue running")
            print("4. Quit")
            
            try:
                choice = input("\nEnter choice (1-4): ").strip()
                if choice == '1':
                    view_current_events()
                    print("\n[CONTINUE] Bot continuing...")
                elif choice == '2':
                    print("[MANUAL] Sending manual report...")
                    send_trading_report()
                    print("\n[CONTINUE] Bot continuing...")
                elif choice == '3':
                    print("[CONTINUE] Bot continuing...")
                elif choice == '4':
                    print("[SHUTDOWN] Bot stopped by user")
                    break
                else:
                    print("[INVALID] Invalid choice, continuing...")
            except:
                print("[CONTINUE] Bot continuing...")
        except Exception as e:
            print(f"[ERROR] Main loop exception: {e}")
            time.sleep(30)  # Wait before retrying

if __name__ == "__main__":
    main_loop()
