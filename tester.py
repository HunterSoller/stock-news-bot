#!/usr/bin/env python3
"""
Stock News Bot Filter Tester

This script allows you to test the filtering system by pulling articles
from RSS feeds and showing which ones pass through the filters.
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

def print_filter_status():
    """Print current filter configuration status"""
    print("=" * 80)
    print("🔧 CURRENT FILTER CONFIGURATION")
    print("=" * 80)
    
    filters = [
        ("Sentiment Filtering", ENABLE_SENTIMENT_FILTERING),
        ("Ticker Filtering", ENABLE_TICKER_FILTERING),
        ("Length Filtering", ENABLE_LENGTH_FILTERING),
        ("Time Filtering", ENABLE_TIME_FILTERING),
        ("Sector Filtering", ENABLE_SECTOR_FILTERING),
        ("Importance Filtering", ENABLE_IMPORTANCE_FILTERING),
        ("Duplicate Filtering", ENABLE_DUPLICATE_FILTERING),
        ("Blacklist Filtering", ENABLE_BLACKLIST_FILTERING),
        ("Volume Filtering", ENABLE_VOLUME_FILTERING),
    ]
    
    for name, enabled in filters:
        status = "✅ ENABLED" if enabled else "❌ DISABLED"
        print(f"{name:<25} {status}")
    
    print(f"\n📊 THRESHOLDS:")
    print(f"Min Importance Score: {MIN_IMPORTANCE_SCORE}")
    print(f"Min Sentiment Strength: {MIN_SENTIMENT_STRENGTH}")
    print(f"Max Articles Per Feed: {MAX_ARTICLES_PER_FEED}")
    print(f"Max Alerts Per Batch: {MAX_ALERTS_PER_BATCH}")
    
    print(f"\n🎯 SENTIMENT SETTINGS:")
    print(f"Sentiment Threshold: {'✅ ENABLED' if ENABLE_SENTIMENT_THRESHOLD else '❌ DISABLED'}")
    print(f"Mixed Sentiment: {'✅ ALLOWED' if ENABLE_MIXED_SENTIMENT_FILTERING else '❌ BLOCKED'}")
    print(f"Neutral Sentiment: {'✅ ALLOWED' if ENABLE_NEUTRAL_SENTIMENT else '❌ BLOCKED'}")
    
    print(f"\n📈 ENABLED KEYWORDS:")
    bullish_count = sum(1 for v in BULLISH_KEYWORDS.values() if v)
    bearish_count = sum(1 for v in BEARISH_KEYWORDS.values() if v)
    earnings_count = sum(1 for v in EARNINGS_KEYWORDS.values() if v)
    breaking_count = sum(1 for v in BREAKING_NEWS_KEYWORDS.values() if v)
    
    print(f"Bullish Keywords: {bullish_count}/{len(BULLISH_KEYWORDS)}")
    print(f"Bearish Keywords: {bearish_count}/{len(BEARISH_KEYWORDS)}")
    print(f"Earnings Keywords: {earnings_count}/{len(EARNINGS_KEYWORDS)}")
    print(f"Breaking News Keywords: {breaking_count}/{len(BREAKING_NEWS_KEYWORDS)}")
    print("=" * 80)

def test_article(title, link="", article_date=""):
    """Test a single article through all filters"""
    print(f"\n📰 TESTING ARTICLE:")
    print(f"Title: {title}")
    if link:
        print(f"Link: {link}")
    if article_date:
        print(f"Date: {article_date}")
    print("-" * 60)
    
    # Clean the title
    clean_title = clean(title)
    print(f"✅ Cleaned Title: {clean_title}")
    
    # Test each filter step by step
    filters_passed = []
    filters_failed = []
    
    # 1. Length filtering
    if ENABLE_LENGTH_FILTERING:
        if filter_by_length(clean_title):
            filters_passed.append("Length")
        else:
            filters_failed.append("Length")
    else:
        filters_passed.append("Length (disabled)")
    
    # 2. Time filtering
    if ENABLE_TIME_FILTERING and article_date:
        if filter_by_time(article_date):
            filters_passed.append("Time")
        else:
            filters_failed.append("Time")
    else:
        filters_passed.append("Time (disabled)")
    
    # 3. Blacklist filtering
    if ENABLE_BLACKLIST_FILTERING:
        if filter_by_blacklist(clean_title):
            filters_passed.append("Blacklist")
        else:
            filters_failed.append("Blacklist")
    else:
        filters_passed.append("Blacklist (disabled)")
    
    # 4. Ticker extraction
    ticker = extract_ticker(clean_title)
    if ENABLE_TICKER_FILTERING:
        if ticker:
            filters_passed.append(f"Ticker ({ticker})")
        else:
            filters_failed.append("Ticker")
    else:
        filters_passed.append("Ticker (disabled)")
    
    # 5. Sector filtering
    if ENABLE_SECTOR_FILTERING and ticker:
        if filter_by_sector(ticker):
            filters_passed.append("Sector")
        else:
            filters_failed.append("Sector")
    else:
        filters_passed.append("Sector (disabled)")
    
    # 6. Volume filtering
    if ENABLE_VOLUME_FILTERING and ticker:
        if check_volume_filter(ticker):
            filters_passed.append("Volume")
        else:
            filters_failed.append("Volume")
    else:
        filters_passed.append("Volume (disabled)")
    
    # 7. Sentiment classification
    sentiment = classify_sentiment(clean_title)
    if ENABLE_SENTIMENT_FILTERING:
        if sentiment != "NEUTRAL" or ENABLE_NEUTRAL_SENTIMENT:
            filters_passed.append(f"Sentiment ({sentiment})")
        else:
            filters_failed.append("Sentiment")
    else:
        filters_passed.append("Sentiment (disabled)")
    
    # 8. Importance scoring
    score = importance_score(clean_title, ticker)
    if ENABLE_IMPORTANCE_FILTERING:
        if score >= MIN_IMPORTANCE_SCORE:
            filters_passed.append(f"Importance (score: {score})")
        else:
            filters_failed.append(f"Importance (score: {score})")
    else:
        filters_passed.append("Importance (disabled)")
    
    # Print results
    print(f"\n✅ FILTERS PASSED ({len(filters_passed)}):")
    for filter_name in filters_passed:
        print(f"   • {filter_name}")
    
    if filters_failed:
        print(f"\n❌ FILTERS FAILED ({len(filters_failed)}):")
        for filter_name in filters_failed:
            print(f"   • {filter_name}")
    
    # Overall result
    overall_result = len(filters_failed) == 0
    print(f"\n🎯 OVERALL RESULT: {'✅ PASSED' if overall_result else '❌ FAILED'}")
    
    if overall_result:
        print(f"📤 This article would be sent as: *{sentiment}* ${ticker}")
        print(f"📊 Importance Score: {score}")
    
    return overall_result, sentiment, ticker, score

def scan_feeds_for_testing(feed_list, max_articles=20):
    """Scan feeds and return articles for testing"""
    print(f"\n🔍 SCANNING {len(feed_list)} FEEDS...")
    articles = []
    
    for url in feed_list:
        try:
            feed = feedparser.parse(url)
            print(f"📡 {url}: {len(feed.entries)} entries")
            
            for i, entry in enumerate(feed.entries[:max_articles]):
                title = clean(entry.get("title", ""))
                link = entry.get("link", "")
                article_date = entry.get("published", "")
                
                if title:
                    articles.append({
                        'title': title,
                        'link': link,
                        'date': article_date,
                        'source': url
                    })
        except Exception as e:
            print(f"❌ Error parsing {url}: {e}")
    
    print(f"📰 Found {len(articles)} articles to test")
    return articles

def run_comprehensive_test():
    """Run a comprehensive test on all feeds"""
    print("🚀 STARTING COMPREHENSIVE FILTER TEST")
    print_filter_status()
    
    # Test market feeds
    print(f"\n📈 TESTING MARKET FEEDS...")
    market_articles = scan_feeds_for_testing(FEEDS_MARKET, max_articles=10)
    
    passed_articles = []
    failed_articles = []
    
    for i, article in enumerate(market_articles, 1):
        print(f"\n{'='*80}")
        print(f"ARTICLE {i}/{len(market_articles)}")
        
        passed, sentiment, ticker, score = test_article(
            article['title'], 
            article['link'], 
            article['date']
        )
        
        if passed:
            passed_articles.append({
                'title': article['title'],
                'sentiment': sentiment,
                'ticker': ticker,
                'score': score,
                'source': article['source']
            })
        else:
            failed_articles.append(article)
    
    # Test biotech feeds
    print(f"\n🧬 TESTING BIOTECH FEEDS...")
    biotech_articles = scan_feeds_for_testing(FEEDS_BIOTECH, max_articles=10)
    
    for i, article in enumerate(biotech_articles, 1):
        print(f"\n{'='*80}")
        print(f"BIOTECH ARTICLE {i}/{len(biotech_articles)}")
        
        passed, sentiment, ticker, score = test_article(
            article['title'], 
            article['link'], 
            article['date']
        )
        
        if passed:
            passed_articles.append({
                'title': article['title'],
                'sentiment': sentiment,
                'ticker': ticker,
                'score': score,
                'source': article['source']
            })
        else:
            failed_articles.append(article)
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Total Articles Tested: {len(market_articles) + len(biotech_articles)}")
    print(f"Articles Passed: {len(passed_articles)}")
    print(f"Articles Failed: {len(failed_articles)}")
    print(f"Pass Rate: {len(passed_articles)/(len(market_articles) + len(biotech_articles))*100:.1f}%")
    
    if passed_articles:
        print(f"\n✅ ARTICLES THAT WOULD BE SENT:")
        for i, article in enumerate(passed_articles[:10], 1):  # Show top 10
            print(f"{i:2d}. [{article['sentiment']}] ${article['ticker']} (score: {article['score']})")
            print(f"    {article['title'][:80]}...")
    
    if len(passed_articles) == 0:
        print(f"\n⚠️  NO ARTICLES PASSED THE FILTERS!")
        print(f"Consider adjusting your filter settings in main.py")
        print(f"Try disabling some filters or lowering thresholds")

def diagnostic_mode():
    """Run diagnostic mode to analyze filter restrictions"""
    print("\n🔍 DIAGNOSTIC MODE - ANALYZING FILTER RESTRICTIONS")
    print("=" * 80)
    
    # Test with sample articles to identify common issues
    sample_articles = [
        "Apple beats earnings expectations as iPhone sales surge",
        "Tesla stock falls after disappointing quarterly results",
        "Microsoft announces new AI partnership with OpenAI",
        "Breaking: Amazon reports record revenue growth",
        "Johnson & Johnson faces new lawsuit over product safety",
        "Google stock jumps on strong cloud computing performance",
        "Meta warns of declining ad revenue in Q4",
        "NVIDIA soars after AI chip demand exceeds expectations",
        "Bank of America downgrades tech sector outlook",
        "Pfizer launches new COVID vaccine variant"
    ]
    
    print(f"Testing {len(sample_articles)} sample articles to identify filter restrictions...")
    
    # Track filter failure statistics
    filter_stats = {
        'Length': 0,
        'Time': 0,
        'Blacklist': 0,
        'Ticker': 0,
        'Sector': 0,
        'Volume': 0,
        'Sentiment': 0,
        'Importance': 0
    }
    
    total_tested = 0
    total_passed = 0
    
    for i, title in enumerate(sample_articles, 1):
        print(f"\n{'='*60}")
        print(f"SAMPLE {i}/{len(sample_articles)}")
        
        passed, sentiment, ticker, score = test_article(title)
        total_tested += 1
        
        if passed:
            total_passed += 1
        
        # Analyze why it failed (simplified version for diagnostic)
        if not passed:
            clean_title = clean(title)
            
            # Check each filter
            if ENABLE_LENGTH_FILTERING and not filter_by_length(clean_title):
                filter_stats['Length'] += 1
            
            if ENABLE_BLACKLIST_FILTERING and not filter_by_blacklist(clean_title):
                filter_stats['Blacklist'] += 1
            
            ticker = extract_ticker(clean_title)
            if ENABLE_TICKER_FILTERING and not ticker:
                filter_stats['Ticker'] += 1
            
            if ticker and ENABLE_SECTOR_FILTERING and not filter_by_sector(ticker):
                filter_stats['Sector'] += 1
            
            if ticker and ENABLE_VOLUME_FILTERING and not check_volume_filter(ticker):
                filter_stats['Volume'] += 1
            
            sentiment = classify_sentiment(clean_title)
            if ENABLE_SENTIMENT_FILTERING and sentiment == "NEUTRAL" and not ENABLE_NEUTRAL_SENTIMENT:
                filter_stats['Sentiment'] += 1
            
            score = importance_score(clean_title, ticker)
            if ENABLE_IMPORTANCE_FILTERING and score < MIN_IMPORTANCE_SCORE:
                filter_stats['Importance'] += 1
    
    # Print diagnostic results
    print(f"\n{'='*80}")
    print("🔍 DIAGNOSTIC RESULTS")
    print(f"{'='*80}")
    
    pass_rate = (total_passed / total_tested) * 100 if total_tested > 0 else 0
    print(f"📊 Overall Pass Rate: {pass_rate:.1f}% ({total_passed}/{total_tested})")
    
    if pass_rate < 50:
        print(f"\n⚠️  LOW PASS RATE DETECTED!")
        print(f"The following filters are most restrictive:")
        
        # Sort filters by failure count
        sorted_filters = sorted(filter_stats.items(), key=lambda x: x[1], reverse=True)
        
        for filter_name, failure_count in sorted_filters:
            if failure_count > 0:
                percentage = (failure_count / total_tested) * 100
                print(f"   • {filter_name}: {failure_count} failures ({percentage:.1f}% of articles)")
        
        print(f"\n💡 RECOMMENDATIONS:")
        
        # Provide specific recommendations based on failures
        if filter_stats['Ticker'] > total_tested * 0.5:
            print(f"   🔧 TICKER FILTER: {filter_stats['Ticker']} articles failed ticker detection")
            print(f"      - Consider setting ENABLE_TICKER_FILTERING = False")
            print(f"      - Or adjust ALLOW_CASUAL_TICKER_DETECTION = True")
            print(f"      - Or expand TICKER_BLACKLIST")
        
        if filter_stats['Sentiment'] > total_tested * 0.3:
            print(f"   🔧 SENTIMENT FILTER: {filter_stats['Sentiment']} articles classified as neutral")
            print(f"      - Consider setting ENABLE_NEUTRAL_SENTIMENT = True")
            print(f"      - Or lower MIN_SENTIMENT_STRENGTH")
            print(f"      - Or add more keywords to BULLISH_KEYWORDS/BEARISH_KEYWORDS")
        
        if filter_stats['Importance'] > total_tested * 0.4:
            print(f"   🔧 IMPORTANCE FILTER: {filter_stats['Importance']} articles below threshold")
            print(f"      - Consider lowering MIN_IMPORTANCE_SCORE")
            print(f"      - Or increase BULLISH_KEYWORD_WEIGHT/BEARISH_KEYWORD_WEIGHT")
            print(f"      - Or add more keywords to EARNINGS_KEYWORDS")
        
        if filter_stats['Length'] > total_tested * 0.2:
            print(f"   🔧 LENGTH FILTER: {filter_stats['Length']} articles failed length check")
            print(f"      - Consider adjusting MIN_HEADLINE_LENGTH/MAX_HEADLINE_LENGTH")
            print(f"      - Or set ENABLE_LENGTH_FILTERING = False")
        
        if filter_stats['Blacklist'] > total_tested * 0.1:
            print(f"   🔧 BLACKLIST FILTER: {filter_stats['Blacklist']} articles contained blacklisted terms")
            print(f"      - Review GENERAL_BLACKLIST for overly restrictive terms")
            print(f"      - Or set ENABLE_BLACKLIST_FILTERING = False")
    
    else:
        print(f"\n✅ PASS RATE LOOKS GOOD!")
        print(f"Your filters are working well. Consider tightening them if you want fewer articles.")
    
    # Show current filter settings that might be too restrictive
    print(f"\n🔧 CURRENT FILTER SETTINGS ANALYSIS:")
    
    restrictive_settings = []
    
    if MIN_IMPORTANCE_SCORE > 3:
        restrictive_settings.append(f"MIN_IMPORTANCE_SCORE ({MIN_IMPORTANCE_SCORE}) is high")
    
    if MIN_SENTIMENT_STRENGTH > 2:
        restrictive_settings.append(f"MIN_SENTIMENT_STRENGTH ({MIN_SENTIMENT_STRENGTH}) is high")
    
    if not ENABLE_NEUTRAL_SENTIMENT:
        restrictive_settings.append("ENABLE_NEUTRAL_SENTIMENT is False")
    
    if not ENABLE_MIXED_SENTIMENT_FILTERING:
        restrictive_settings.append("ENABLE_MIXED_SENTIMENT_FILTERING is False")
    
    if MAX_ARTICLES_PER_FEED < 20:
        restrictive_settings.append(f"MAX_ARTICLES_PER_FEED ({MAX_ARTICLES_PER_FEED}) is low")
    
    if restrictive_settings:
        print(f"   ⚠️  Potentially restrictive settings:")
        for setting in restrictive_settings:
            print(f"      • {setting}")
    else:
        print(f"   ✅ No obviously restrictive settings detected")
    
    print(f"\n{'='*80}")

def detailed_feed_diagnostic():
    """Run detailed diagnostic on real feed data"""
    print("\n🔬 DETAILED FEED DIAGNOSTIC - REAL DATA ANALYSIS")
    print("=" * 80)
    
    # Get real articles from feeds
    print("📡 Fetching real articles from feeds...")
    all_articles = []
    
    # Test market feeds
    market_articles = scan_feeds_for_testing(FEEDS_MARKET, max_articles=15)
    all_articles.extend(market_articles)
    
    # Test biotech feeds  
    biotech_articles = scan_feeds_for_testing(FEEDS_BIOTECH, max_articles=15)
    all_articles.extend(biotech_articles)
    
    if not all_articles:
        print("❌ No articles found in feeds. Check your internet connection.")
        return
    
    print(f"📰 Analyzing {len(all_articles)} real articles...")
    
    # Detailed analysis
    analysis = {
        'total': len(all_articles),
        'passed': 0,
        'failed': 0,
        'filter_failures': {
            'Length': 0,
            'Time': 0, 
            'Blacklist': 0,
            'Ticker': 0,
            'Sector': 0,
            'Volume': 0,
            'Sentiment': 0,
            'Importance': 0
        },
        'sentiment_distribution': {
            'BULLISH': 0,
            'BEARISH': 0,
            'NEUTRAL': 0,
            'MIXED': 0
        },
        'ticker_detection': {
            'explicit_format': 0,
            'casual_detection': 0,
            'no_ticker': 0
        },
        'score_distribution': {
            'low': 0,      # 0-2
            'medium': 0,   # 3-5
            'high': 0      # 6+
        }
    }
    
    # Analyze each article
    for i, article in enumerate(all_articles, 1):
        print(f"\n📄 Analyzing article {i}/{len(all_articles)}")
        print(f"Title: {article['title'][:60]}...")
        
        clean_title = clean(article['title'])
        ticker = extract_ticker(clean_title)
        sentiment = classify_sentiment(clean_title)
        score = importance_score(clean_title, ticker)
        
        # Track sentiment distribution
        analysis['sentiment_distribution'][sentiment] += 1
        
        # Track ticker detection
        if ticker:
            if '$' in article['title'] or '(' in article['title']:
                analysis['ticker_detection']['explicit_format'] += 1
            else:
                analysis['ticker_detection']['casual_detection'] += 1
        else:
            analysis['ticker_detection']['no_ticker'] += 1
        
        # Track score distribution
        if score <= 2:
            analysis['score_distribution']['low'] += 1
        elif score <= 5:
            analysis['score_distribution']['medium'] += 1
        else:
            analysis['score_distribution']['high'] += 1
        
        # Test if article passes all filters
        passed = True
        
        # Check each filter
        if ENABLE_LENGTH_FILTERING and not filter_by_length(clean_title):
            analysis['filter_failures']['Length'] += 1
            passed = False
        
        if ENABLE_TIME_FILTERING and article['date'] and not filter_by_time(article['date']):
            analysis['filter_failures']['Time'] += 1
            passed = False
        
        if ENABLE_BLACKLIST_FILTERING and not filter_by_blacklist(clean_title):
            analysis['filter_failures']['Blacklist'] += 1
            passed = False
        
        if ENABLE_TICKER_FILTERING and not ticker:
            analysis['filter_failures']['Ticker'] += 1
            passed = False
        
        if ticker and ENABLE_SECTOR_FILTERING and not filter_by_sector(ticker):
            analysis['filter_failures']['Sector'] += 1
            passed = False
        
        if ticker and ENABLE_VOLUME_FILTERING and not check_volume_filter(ticker):
            analysis['filter_failures']['Volume'] += 1
            passed = False
        
        if ENABLE_SENTIMENT_FILTERING and sentiment == "NEUTRAL" and not ENABLE_NEUTRAL_SENTIMENT:
            analysis['filter_failures']['Sentiment'] += 1
            passed = False
        
        if ENABLE_IMPORTANCE_FILTERING and score < MIN_IMPORTANCE_SCORE:
            analysis['filter_failures']['Importance'] += 1
            passed = False
        
        if passed:
            analysis['passed'] += 1
        else:
            analysis['failed'] += 1
    
    # Print detailed results
    print(f"\n{'='*80}")
    print("🔬 DETAILED DIAGNOSTIC RESULTS")
    print(f"{'='*80}")
    
    pass_rate = (analysis['passed'] / analysis['total']) * 100
    print(f"📊 Overall Pass Rate: {pass_rate:.1f}% ({analysis['passed']}/{analysis['total']})")
    
    print(f"\n📈 SENTIMENT DISTRIBUTION:")
    for sentiment, count in analysis['sentiment_distribution'].items():
        percentage = (count / analysis['total']) * 100
        print(f"   • {sentiment}: {count} articles ({percentage:.1f}%)")
    
    print(f"\n🎯 TICKER DETECTION ANALYSIS:")
    for method, count in analysis['ticker_detection'].items():
        percentage = (count / analysis['total']) * 100
        print(f"   • {method.replace('_', ' ').title()}: {count} articles ({percentage:.1f}%)")
    
    print(f"\n⭐ IMPORTANCE SCORE DISTRIBUTION:")
    for level, count in analysis['score_distribution'].items():
        percentage = (count / analysis['total']) * 100
        print(f"   • {level.title()}: {count} articles ({percentage:.1f}%)")
    
    print(f"\n🚫 FILTER FAILURE ANALYSIS:")
    total_failures = sum(analysis['filter_failures'].values())
    if total_failures > 0:
        for filter_name, failures in analysis['filter_failures'].items():
            if failures > 0:
                percentage = (failures / analysis['total']) * 100
                print(f"   • {filter_name}: {failures} failures ({percentage:.1f}% of articles)")
    
    # Recommendations based on real data
    print(f"\n💡 RECOMMENDATIONS BASED ON REAL DATA:")
    
    if pass_rate < 30:
        print(f"   🚨 CRITICAL: Very low pass rate ({pass_rate:.1f}%)")
        print(f"      Your filters are too restrictive for real market data")
        
        # Find the most problematic filters
        worst_filters = sorted(analysis['filter_failures'].items(), key=lambda x: x[1], reverse=True)
        for filter_name, failures in worst_filters[:3]:
            if failures > analysis['total'] * 0.3:  # More than 30% failure rate
                print(f"      🔧 Consider disabling or adjusting {filter_name} filter")
    
    elif pass_rate < 50:
        print(f"   ⚠️  MODERATE: Low pass rate ({pass_rate:.1f}%)")
        print(f"      Consider loosening some filter settings")
    
    else:
        print(f"   ✅ GOOD: Pass rate looks reasonable ({pass_rate:.1f}%)")
    
    # Specific recommendations
    if analysis['ticker_detection']['no_ticker'] > analysis['total'] * 0.4:
        print(f"   🔧 TICKER ISSUE: {analysis['ticker_detection']['no_ticker']} articles have no detectable ticker")
        print(f"      Consider: ENABLE_TICKER_FILTERING = False or ALLOW_CASUAL_TICKER_DETECTION = True")
    
    if analysis['sentiment_distribution']['NEUTRAL'] > analysis['total'] * 0.5:
        print(f"   🔧 SENTIMENT ISSUE: {analysis['sentiment_distribution']['NEUTRAL']} articles are neutral")
        print(f"      Consider: ENABLE_NEUTRAL_SENTIMENT = True")
    
    if analysis['score_distribution']['low'] > analysis['total'] * 0.6:
        print(f"   🔧 SCORE ISSUE: {analysis['score_distribution']['low']} articles have low importance scores")
        print(f"      Consider: Lowering MIN_IMPORTANCE_SCORE or adding more keywords")
    
    print(f"\n{'='*80}")

def test_custom_article():
    """Test a custom article entered by user"""
    print("\n📝 CUSTOM ARTICLE TEST")
    print("Enter a headline to test (or 'quit' to exit):")
    
    while True:
        title = input("\nHeadline: ").strip()
        if title.lower() == 'quit':
            break
        
        if not title:
            print("Please enter a headline")
            continue
        
        test_article(title)

def main():
    """Main tester interface"""
    print("🤖 STOCK NEWS BOT FILTER TESTER")
    print("=" * 50)
    
    while True:
        print("\nChoose an option:")
        print("1. Show current filter configuration")
        print("2. Test custom article")
        print("3. Run comprehensive test on all feeds")
        print("4. 🔍 DIAGNOSTIC MODE - Analyze filter restrictions")
        print("5. 🔬 DETAILED FEED DIAGNOSTIC - Real data analysis")
        print("6. Exit")
        
        choice = input("\nEnter choice (1-6): ").strip()
        
        if choice == '1':
            print_filter_status()
        elif choice == '2':
            test_custom_article()
        elif choice == '3':
            run_comprehensive_test()
        elif choice == '4':
            diagnostic_mode()
        elif choice == '5':
            detailed_feed_diagnostic()
        elif choice == '6':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-6.")

if __name__ == "__main__":
    main()
