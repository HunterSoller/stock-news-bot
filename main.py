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
