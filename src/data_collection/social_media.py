"""Social media data collection (Twitter, Reddit)."""

import tweepy
import praw
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SocialMediaCollector:
    """Collect social media data from Twitter and Reddit."""
    
    def __init__(
        self,
        twitter_config: Optional[Dict] = None,
        reddit_config: Optional[Dict] = None
    ):
        """
        Initialize social media collectors.
        
        Args:
            twitter_config: Twitter API credentials
            reddit_config: Reddit API credentials
        """
        self.twitter_client = None
        self.reddit_client = None
        
        if twitter_config and twitter_config.get('enabled', False):
            try:
                auth = tweepy.OAuthHandler(
                    twitter_config.get('api_key', ''),
                    twitter_config.get('api_secret', '')
                )
                auth.set_access_token(
                    twitter_config.get('access_token', ''),
                    twitter_config.get('access_token_secret', '')
                )
                self.twitter_client = tweepy.API(auth, wait_on_rate_limit=True)
                logger.info("Twitter client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Twitter client: {e}")
        
        if reddit_config and reddit_config.get('enabled', False):
            try:
                # Reddit can work without credentials for read-only access
                self.reddit_client = praw.Reddit(
                    client_id=reddit_config.get('client_id', ''),
                    client_secret=reddit_config.get('client_secret', ''),
                    user_agent=reddit_config.get('user_agent', 'TradingAI/1.0')
                )
                # Test connection
                _ = self.reddit_client.subreddit('test').id
                logger.info("Reddit client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Reddit client: {e}")
                self.reddit_client = None
    
    def collect_twitter_data(
        self,
        search_terms: List[str],
        max_tweets: int = 100,
        hours_back: int = 24
    ) -> pd.DataFrame:
        """
        Collect tweets related to search terms.
        
        Args:
            search_terms: List of terms to search
            max_tweets: Maximum number of tweets to collect
            hours_back: Hours to look back
        
        Returns:
            DataFrame with tweet data
        """
        if not self.twitter_client:
            # Silently return empty DataFrame if Twitter is not configured
            return pd.DataFrame()
        
        # Test if client is actually working
        try:
            # Quick test to verify authentication
            _ = self.twitter_client.verify_credentials()
        except Exception as e:
            # Client exists but authentication failed - don't spam logs
            return pd.DataFrame()
        
        tweets_data = []
        since_date = datetime.now() - timedelta(hours=hours_back)
        
        try:
            for term in search_terms:
                try:
                    tweets = tweepy.Cursor(
                        self.twitter_client.search_tweets,
                        q=term,
                        lang='en',
                        result_type='recent',
                        tweet_mode='extended'
                    ).items(max_tweets // len(search_terms))
                    
                    for tweet in tweets:
                        if tweet.created_at >= since_date:
                            tweets_data.append({
                                'timestamp': tweet.created_at,
                                'text': tweet.full_text,
                                'user': tweet.user.screen_name,
                                'retweets': tweet.retweet_count,
                                'likes': tweet.favorite_count,
                                'followers': tweet.user.followers_count,
                                'search_term': term
                            })
                except Exception as e:
                    # Only log if it's not an authentication error (expected)
                    error_str = str(e)
                    if "215" not in error_str and "Bad Authentication" not in error_str:
                        logger.error(f"Error collecting tweets for {term}: {e}")
                    # Silently skip authentication errors
                    continue
            
            df = pd.DataFrame(tweets_data)
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
            
        except Exception as e:
            logger.error(f"Error in Twitter collection: {e}")
            return pd.DataFrame()
    
    def collect_reddit_data(
        self,
        subreddits: List[str],
        max_posts: int = 50,
        hours_back: int = 24
    ) -> pd.DataFrame:
        """
        Collect Reddit posts from specified subreddits.
        
        Args:
            subreddits: List of subreddit names
            max_posts: Maximum posts per subreddit
            hours_back: Hours to look back
        
        Returns:
            DataFrame with Reddit post data
        """
        if not self.reddit_client:
            logger.warning("Reddit client not initialized - skipping Reddit data")
            return pd.DataFrame()
        
        posts_data = []
        since_timestamp = (datetime.now() - timedelta(hours=hours_back)).timestamp()
        
        try:
            for subreddit_name in subreddits:
                try:
                    subreddit = self.reddit_client.subreddit(subreddit_name)
                    posts = subreddit.new(limit=max_posts)
                    
                    for post in posts:
                        if post.created_utc >= since_timestamp:
                            posts_data.append({
                                'timestamp': datetime.fromtimestamp(post.created_utc),
                                'title': post.title,
                                'text': post.selftext,
                                'score': post.score,
                                'comments': post.num_comments,
                                'subreddit': subreddit_name,
                                'url': post.url
                            })
                except Exception as e:
                    logger.error(f"Error collecting from r/{subreddit_name}: {e}")
                    continue
            
            df = pd.DataFrame(posts_data)
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
            
        except Exception as e:
            logger.error(f"Error in Reddit collection: {e}")
            return pd.DataFrame()
    
    def extract_crypto_mentions(self, text: str, symbols: List[str]) -> Dict[str, int]:
        """Extract mentions of cryptocurrency symbols from text."""
        mentions = {}
        text_upper = text.upper()
        
        for symbol in symbols:
            # Count mentions (case-insensitive)
            pattern = rf'\b{re.escape(symbol)}\b'
            count = len(re.findall(pattern, text_upper, re.IGNORECASE))
            if count > 0:
                mentions[symbol] = count
        
        return mentions

