"""Sentiment analysis features from social media and news."""

import pandas as pd
import numpy as np
from typing import Dict, List
from textblob import TextBlob
import re


class SentimentAnalyzer:
    """Analyze sentiment from social media and news data."""
    
    def __init__(self):
        """Initialize sentiment analyzer."""
        # Crypto-specific keywords
        self.positive_keywords = [
            'bullish', 'moon', 'pump', 'rally', 'surge', 'breakout',
            'adoption', 'partnership', 'upgrade', 'halving', 'accumulate'
        ]
        self.negative_keywords = [
            'bearish', 'dump', 'crash', 'correction', 'sell', 'fud',
            'hack', 'regulation', 'ban', 'scam', 'liquidation'
        ]
    
    def analyze_text_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of a text.
        
        Args:
            text: Text to analyze
        
        Returns:
            Dictionary with sentiment scores
        """
        if not text or pd.isna(text):
            return {
                'polarity': 0.0,
                'subjectivity': 0.0,
                'crypto_sentiment': 0.0
            }
        
        # TextBlob sentiment
        blob = TextBlob(str(text))
        polarity = blob.sentiment.polarity  # -1 to 1
        subjectivity = blob.sentiment.subjectivity  # 0 to 1
        
        # Crypto-specific sentiment
        text_lower = text.lower()
        positive_count = sum(1 for word in self.positive_keywords if word in text_lower)
        negative_count = sum(1 for word in self.negative_keywords if word in text_lower)
        
        crypto_sentiment = (positive_count - negative_count) / max(len(text.split()), 1)
        crypto_sentiment = np.clip(crypto_sentiment, -1, 1)
        
        return {
            'polarity': polarity,
            'subjectivity': subjectivity,
            'crypto_sentiment': crypto_sentiment,
            'positive_keywords': positive_count,
            'negative_keywords': negative_count
        }
    
    def aggregate_sentiment(
        self,
        df: pd.DataFrame,
        text_column: str = 'text',
        timestamp_column: str = 'timestamp',
        window_hours: int = 24
    ) -> pd.DataFrame:
        """
        Aggregate sentiment over time windows.
        
        Args:
            df: DataFrame with text data
            text_column: Column name with text
            timestamp_column: Column name with timestamps
            window_hours: Time window in hours
        
        Returns:
            DataFrame with aggregated sentiment features
        """
        if df.empty:
            return pd.DataFrame()
        
        # Analyze sentiment for each row
        sentiments = df[text_column].apply(self.analyze_text_sentiment)
        sentiment_df = pd.DataFrame(list(sentiments))
        
        # Add timestamp
        sentiment_df[timestamp_column] = pd.to_datetime(df[timestamp_column])
        sentiment_df.set_index(timestamp_column, inplace=True)
        
        # Aggregate by time windows (use 'h' instead of 'H' for pandas compatibility)
        aggregated = sentiment_df.resample(f'{window_hours}h').agg({
            'polarity': ['mean', 'std', 'count'],
            'subjectivity': 'mean',
            'crypto_sentiment': ['mean', 'std'],
            'positive_keywords': 'sum',
            'negative_keywords': 'sum'
        })
        
        # Flatten column names
        aggregated.columns = ['_'.join(col).strip() for col in aggregated.columns.values]
        
        return aggregated
    
    def calculate_sentiment_features(
        self,
        twitter_df: pd.DataFrame,
        reddit_df: pd.DataFrame,
        news_df: pd.DataFrame,
        symbol: str
    ) -> Dict[str, float]:
        """
        Calculate comprehensive sentiment features.
        
        Args:
            twitter_df: Twitter data
            reddit_df: Reddit data
            news_df: News data
            symbol: Cryptocurrency symbol
        
        Returns:
            Dictionary of sentiment features
        """
        features = {}
        
        # Twitter sentiment
        if not twitter_df.empty:
            twitter_sentiment = self.aggregate_sentiment(twitter_df, 'text', 'timestamp')
            if not twitter_sentiment.empty:
                latest = twitter_sentiment.iloc[-1]
                features['twitter_sentiment'] = latest.get('crypto_sentiment_mean', 0.0)
                features['twitter_polarity'] = latest.get('polarity_mean', 0.0)
                features['twitter_volume'] = latest.get('polarity_count', 0.0)
        
        # Reddit sentiment
        if not reddit_df.empty:
            reddit_sentiment = self.aggregate_sentiment(reddit_df, 'text', 'timestamp')
            if not reddit_sentiment.empty:
                latest = reddit_sentiment.iloc[-1]
                features['reddit_sentiment'] = latest.get('crypto_sentiment_mean', 0.0)
                features['reddit_polarity'] = latest.get('polarity_mean', 0.0)
                features['reddit_volume'] = latest.get('polarity_count', 0.0)
        
        # News sentiment
        if not news_df.empty:
            news_sentiment = self.aggregate_sentiment(news_df, 'text', 'timestamp')
            if not news_sentiment.empty:
                latest = news_sentiment.iloc[-1]
                features['news_sentiment'] = latest.get('crypto_sentiment_mean', 0.0)
                features['news_polarity'] = latest.get('polarity_mean', 0.0)
                features['news_volume'] = latest.get('polarity_count', 0.0)
        
        # Combined sentiment
        sentiment_scores = [
            features.get('twitter_sentiment', 0),
            features.get('reddit_sentiment', 0),
            features.get('news_sentiment', 0)
        ]
        features['combined_sentiment'] = np.mean([s for s in sentiment_scores if s != 0]) if any(s != 0 for s in sentiment_scores) else 0.0
        
        return features

