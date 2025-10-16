#!/usr/bin/env python3
"""
Quick debug script to identify why no articles are passing through filters
"""

import os
import sys
import feedparser
from datetime import datetime as dt
from dateutil.tz import gettz

# Add the main directory to the path so we can import from main.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import all the filtering functions and variables from main.py
from main import (
    # Filtering functions
    clean, extract_ticker, classify_sentiment, importance_score,
    filter_by_length, filter_by_time, filter_by_blacklist, 
    filter_by_sector, check_volume_filter,
    
    # Configuration variables
    FEEDS_MARKET, FEEDS_BIOTECH,
    BULLISH_KEYWORDS, BEARISH_KEYWORDS, EARNINGS_KEYWORDS, BREAKING_NEWS_KEYWORDS,
    ENABLE_SENTIMENT_FILTERING, ENABLE_TICKER_FILTERING, ENABLE_LENGTH_FILTERING,
    ENABLE_TIME_FILTERING, ENABLE_SECTOR_FILTERING, ENABLE_IMPORTANCE_FILTERING,
    ENABLE_DUPLICATE_FILTERING, ENABLE_BLACKLIST_FILTERING, ENABLE_VOLUME_FILTERING,
    MIN_IMPORTANCE_SCORE, MIN_SENTIMENT_STRENGTH, ENABLE_SENTIMENT_THRESHOLD,
    ENABLE_MIXED_SENTIMENT_FILTERING, ENABLE_NEUTRAL_SENTIMENT,
    MAX_ARTICLES_PER_FEED, MAX_ALERTS_PER_BATCH,
    
    # Timezone
    ET
)

def debug_filters():
    """Debug why no articles are passing through filters"""
    print("🔍 DEBUGGING FILTER RESTRICTIONS")
    print("=" * 60)
    
    # Test with a few sample articles first
    sample_articles = [
        "Apple beats earnings expectations as iPhone sales surge",
        "Tesla stock falls after disappointing quarterly results", 
        "Microsoft announces new AI partnership with OpenAI",
        "Breaking: Amazon reports record revenue growth",
        "Johnson & Johnson faces new lawsuit over product safety"
    ]
    
    print(f"\n📝 TESTING SAMPLE ARTICLES:")
    for i, title in enumerate(sample_articles, 1):
        print(f"\n{i}. Testing: {title}")
        
        clean_title = clean(title)
        ticker = extract_ticker(clean_title)
        sentiment = classify_sentiment(clean_title)
        score = importance_score(clean_title, ticker)
        
        print(f"   Cleaned: {clean_title}")
        print(f"   Ticker: {ticker}")
        print(f"   Sentiment: {sentiment}")
        print(f"   Score: {score}")
        
        # Check each filter
        filters_failed = []
        
        if ENABLE_LENGTH_FILTERING and not filter_by_length(clean_title):
            filters_failed.append("Length")
        
        if ENABLE_BLACKLIST_FILTERING and not filter_by_blacklist(clean_title):
            filters_failed.append("Blacklist")
        
        if ENABLE_TICKER_FILTERING and not ticker:
            filters_failed.append("Ticker")
        
        if ticker and ENABLE_SECTOR_FILTERING and not filter_by_sector(ticker):
            filters_failed.append("Sector")
        
        if ticker and ENABLE_VOLUME_FILTERING and not check_volume_filter(ticker):
            filters_failed.append("Volume")
        
        if ENABLE_SENTIMENT_FILTERING and sentiment == "NEUTRAL" and not ENABLE_NEUTRAL_SENTIMENT:
            filters_failed.append("Sentiment")
        
        if ENABLE_IMPORTANCE_FILTERING and score < MIN_IMPORTANCE_SCORE:
            filters_failed.append("Importance")
        
        if filters_failed:
            print(f"   ❌ FAILED: {', '.join(filters_failed)}")
        else:
            print(f"   ✅ PASSED")
    
    # Now test real feed data
    print(f"\n📡 TESTING REAL FEED DATA:")
    
    for url in FEEDS_MARKET[:1]:  # Test just one feed first
        try:
            feed = feedparser.parse(url)
            print(f"\nFeed: {url}")
            print(f"Entries: {len(feed.entries)}")
            
            if len(feed.entries) == 0:
                print("   ❌ No entries found")
                continue
            
            # Test first few articles
            for i, entry in enumerate(feed.entries[:5]):
                title = clean(entry.get("title", ""))
                link = entry.get("link", "")
                article_date = entry.get("published", "")
                
                if not title:
                    print(f"   {i+1}. ❌ No title")
                    continue
                
                print(f"   {i+1}. Title: {title[:60]}...")
                
                ticker = extract_ticker(title)
                sentiment = classify_sentiment(title)
                score = importance_score(title, ticker)
                
                print(f"      Ticker: {ticker}")
                print(f"      Sentiment: {sentiment}")
                print(f"      Score: {score}")
                
                # Check each filter step by step
                filters_failed = []
                
                if ENABLE_LENGTH_FILTERING and not filter_by_length(title):
                    filters_failed.append("Length")
                
                if ENABLE_TIME_FILTERING and article_date and not filter_by_time(article_date):
                    filters_failed.append("Time")
                
                if ENABLE_BLACKLIST_FILTERING and not filter_by_blacklist(title):
                    filters_failed.append("Blacklist")
                
                if ENABLE_TICKER_FILTERING and not ticker:
                    filters_failed.append("Ticker")
                
                if ticker and ENABLE_SECTOR_FILTERING and not filter_by_sector(ticker):
                    filters_failed.append("Sector")
                
                if ticker and ENABLE_VOLUME_FILTERING and not check_volume_filter(ticker):
                    filters_failed.append("Volume")
                
                if ENABLE_SENTIMENT_FILTERING and sentiment == "NEUTRAL" and not ENABLE_NEUTRAL_SENTIMENT:
                    filters_failed.append("Sentiment")
                
                if ENABLE_IMPORTANCE_FILTERING and score < MIN_IMPORTANCE_SCORE:
                    filters_failed.append("Importance")
                
                if filters_failed:
                    print(f"      ❌ FAILED: {', '.join(filters_failed)}")
                else:
                    print(f"      ✅ PASSED")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Show current filter settings
    print(f"\n🔧 CURRENT FILTER SETTINGS:")
    print(f"ENABLE_SENTIMENT_FILTERING: {ENABLE_SENTIMENT_FILTERING}")
    print(f"ENABLE_TICKER_FILTERING: {ENABLE_TICKER_FILTERING}")
    print(f"ENABLE_LENGTH_FILTERING: {ENABLE_LENGTH_FILTERING}")
    print(f"ENABLE_TIME_FILTERING: {ENABLE_TIME_FILTERING}")
    print(f"ENABLE_SECTOR_FILTERING: {ENABLE_SECTOR_FILTERING}")
    print(f"ENABLE_IMPORTANCE_FILTERING: {ENABLE_IMPORTANCE_FILTERING}")
    print(f"ENABLE_DUPLICATE_FILTERING: {ENABLE_DUPLICATE_FILTERING}")
    print(f"ENABLE_BLACKLIST_FILTERING: {ENABLE_BLACKLIST_FILTERING}")
    print(f"ENABLE_VOLUME_FILTERING: {ENABLE_VOLUME_FILTERING}")
    print(f"MIN_IMPORTANCE_SCORE: {MIN_IMPORTANCE_SCORE}")
    print(f"MIN_SENTIMENT_STRENGTH: {MIN_SENTIMENT_STRENGTH}")
    print(f"ENABLE_NEUTRAL_SENTIMENT: {ENABLE_NEUTRAL_SENTIMENT}")
    print(f"ENABLE_MIXED_SENTIMENT_FILTERING: {ENABLE_MIXED_SENTIMENT_FILTERING}")
    
    print(f"\n💡 QUICK FIXES TO TRY:")
    print(f"1. Set MIN_IMPORTANCE_SCORE = 0")
    print(f"2. Set ENABLE_NEUTRAL_SENTIMENT = True")
    print(f"3. Set ENABLE_TICKER_FILTERING = False")
    print(f"4. Set ENABLE_SENTIMENT_FILTERING = False")

if __name__ == "__main__":
    debug_filters()
