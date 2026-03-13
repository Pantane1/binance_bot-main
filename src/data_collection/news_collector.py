"""News data collection from various sources."""

import requests
import feedparser
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Optional import for article parsing
try:
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False
    logger.warning("newspaper3k not available - article text extraction will be limited to RSS summaries")


class NewsCollector:
    """Collect news articles from various cryptocurrency news sources."""
    
    def __init__(self, sources: Optional[List[str]] = None):
        """
        Initialize news collector.
        
        Args:
            sources: List of news sources to use
        """
        self.sources = sources or []
        self.rss_feeds = {
            'coindesk': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
            'cointelegraph': 'https://cointelegraph.com/rss',
            'cryptonews': 'https://cryptonews.com/news/feed/',
            'bitcoinmagazine': 'https://bitcoinmagazine.com/.rss/full/',
            'decrypt': 'https://decrypt.co/feed'
        }
    
    def collect_news(
        self,
        max_articles: int = 50,
        hours_back: int = 24,
        keywords: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Collect news articles from configured sources.
        
        Args:
            max_articles: Maximum articles to collect
            hours_back: Hours to look back
            keywords: Keywords to filter articles
        
        Returns:
            DataFrame with news articles
        """
        articles_data = []
        since_date = datetime.now() - timedelta(hours=hours_back)
        
        for source in self.sources:
            if source not in self.rss_feeds:
                logger.warning(f"Unknown news source: {source}")
                continue
            
            try:
                feed_url = self.rss_feeds[source]
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:max_articles // len(self.sources)]:
                    try:
                        # Parse article date
                        article_date = datetime(*entry.published_parsed[:6])
                        
                        if article_date >= since_date:
                            # Try to get full article text
                            article_text = ""
                            if NEWSPAPER_AVAILABLE:
                                try:
                                    article = Article(entry.link)
                                    article.download()
                                    article.parse()
                                    article_text = article.text
                                except:
                                    article_text = entry.get('summary', '')
                            else:
                                article_text = entry.get('summary', '')
                            
                            articles_data.append({
                                'timestamp': article_date,
                                'title': entry.title,
                                'text': article_text or entry.get('summary', ''),
                                'url': entry.link,
                                'source': source,
                                'published': entry.published
                            })
                    except Exception as e:
                        logger.error(f"Error processing article: {e}")
                        continue
                
                # Rate limiting
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error collecting from {source}: {e}")
                continue
        
        df = pd.DataFrame(articles_data)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            # Filter by keywords if provided
            if keywords:
                keyword_filter = df['text'].str.contains(
                    '|'.join(keywords),
                    case=False,
                    na=False
                ) | df['title'].str.contains(
                    '|'.join(keywords),
                    case=False,
                    na=False
                )
                df = df[keyword_filter]
        
        return df
    
    def get_fear_greed_index(self) -> Optional[float]:
        """
        Get Crypto Fear & Greed Index from Alternative.me API.
        
        Returns:
            Fear & Greed Index value (0-100)
        """
        try:
            url = "https://api.alternative.me/fng/"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and len(data['data']) > 0:
                    return float(data['data'][0]['value'])
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {e}")
        
        return None

