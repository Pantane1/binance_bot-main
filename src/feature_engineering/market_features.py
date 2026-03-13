"""Market-specific feature engineering."""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from data_collection.binance_client import BinanceClient


class MarketFeatures:
    """Extract market-specific features."""
    
    def __init__(self, binance_client: BinanceClient):
        """
        Initialize market features extractor.
        
        Args:
            binance_client: Binance client instance
        """
        self.client = binance_client
    
    def get_order_book_features(self, symbol: str, futures: bool = False) -> Dict:
        """
        Extract features from order book.
        
        Args:
            symbol: Trading pair symbol
            futures: Use futures market
        
        Returns:
            Dictionary of order book features
        """
        order_book = self.client.get_order_book(symbol, limit=100, futures=futures)
        
        if not order_book or 'bids' not in order_book:
            return {}
        
        bids = pd.DataFrame(order_book['bids'], columns=['price', 'quantity'])
        asks = pd.DataFrame(order_book['asks'], columns=['price', 'quantity'])
        
        bids['price'] = pd.to_numeric(bids['price'])
        bids['quantity'] = pd.to_numeric(bids['quantity'])
        asks['price'] = pd.to_numeric(asks['price'])
        asks['quantity'] = pd.to_numeric(asks['quantity'])
        
        # Calculate features
        bid_volume = bids['quantity'].sum()
        ask_volume = asks['quantity'].sum()
        total_volume = bid_volume + ask_volume
        
        # Order book imbalance
        imbalance = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0
        
        # Weighted mid price
        bid_weighted = (bids['price'] * bids['quantity']).sum() / bid_volume if bid_volume > 0 else 0
        ask_weighted = (asks['price'] * asks['quantity']).sum() / ask_volume if ask_volume > 0 else 0
        weighted_mid = (bid_weighted + ask_weighted) / 2
        
        # Spread
        spread = asks['price'].iloc[0] - bids['price'].iloc[0]
        spread_pct = (spread / bids['price'].iloc[0]) * 100 if bids['price'].iloc[0] > 0 else 0
        
        # Depth features (liquidity at different levels)
        depth_1pct_bid = bids[bids['price'] >= bids['price'].iloc[0] * 0.99]['quantity'].sum()
        depth_1pct_ask = asks[asks['price'] <= asks['price'].iloc[0] * 1.01]['quantity'].sum()
        
        return {
            'order_book_imbalance': imbalance,
            'bid_volume': bid_volume,
            'ask_volume': ask_volume,
            'spread': spread,
            'spread_pct': spread_pct,
            'weighted_mid_price': weighted_mid,
            'depth_1pct_bid': depth_1pct_bid,
            'depth_1pct_ask': depth_1pct_ask
        }
    
    def get_futures_features(self, symbol: str) -> Dict:
        """
        Extract futures-specific features.
        
        Args:
            symbol: Trading pair symbol
        
        Returns:
            Dictionary of futures features
        """
        features = {}
        
        # Funding rate
        funding_rate = self.client.get_funding_rate(symbol)
        features['funding_rate'] = funding_rate
        
        # Open interest
        open_interest = self.client.get_open_interest(symbol)
        features['open_interest'] = open_interest
        
        # Long/short ratio (would need additional API calls)
        features['long_short_ratio'] = 1.0  # Placeholder
        
        return features
    
    def calculate_volume_profile(self, df: pd.DataFrame, bins: int = 20) -> pd.DataFrame:
        """
        Calculate volume profile.
        
        Args:
            df: DataFrame with OHLCV data
            bins: Number of price bins
        
        Returns:
            DataFrame with volume profile features
        """
        df = df.copy()
        
        # Price range
        price_min = df['low'].min()
        price_max = df['high'].max()
        
        # Create bins
        price_bins = np.linspace(price_min, price_max, bins + 1)
        
        # Calculate volume in each bin
        volume_profile = []
        for i in range(len(price_bins) - 1):
            mask = (df['low'] <= price_bins[i + 1]) & (df['high'] >= price_bins[i])
            volume_in_bin = df.loc[mask, 'volume'].sum()
            volume_profile.append({
                'price_level': (price_bins[i] + price_bins[i + 1]) / 2,
                'volume': volume_in_bin
            })
        
        volume_df = pd.DataFrame(volume_profile)
        
        # Find POC (Point of Control - highest volume level)
        if not volume_df.empty:
            poc_level = volume_df.loc[volume_df['volume'].idxmax(), 'price_level']
            df['POC_distance'] = (df['close'] - poc_level) / df['close']
        else:
            df['POC_distance'] = 0
        
        return df
    
    def calculate_liquidation_levels(self, symbol: str, current_price: float) -> Dict:
        """
        Estimate liquidation levels (simplified).
        
        Args:
            symbol: Trading pair
            current_price: Current market price
        
        Returns:
            Dictionary with estimated liquidation levels
        """
        # This is a simplified version
        # Real implementation would use order book data and position data
        return {
            'estimated_liquidation_long': current_price * 0.90,  # 10% below
            'estimated_liquidation_short': current_price * 1.10,  # 10% above
            'liquidation_distance_pct': 0.10
        }

