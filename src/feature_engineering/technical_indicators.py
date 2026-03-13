"""Technical indicator calculations."""

import pandas as pd
import numpy as np
import ta
from typing import List, Optional


class TechnicalIndicators:
    """Calculate technical indicators for trading."""
    
    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add all technical indicators to dataframe.
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            DataFrame with added indicators
        """
        df = df.copy()
        
        # RSI
        df['RSI'] = ta.momentum.RSIIndicator(df['close']).rsi()
        
        # MACD
        macd = ta.trend.MACD(df['close'])
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
        df['MACD_diff'] = macd.macd_diff()
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df['close'])
        df['BB_high'] = bb.bollinger_hband()
        df['BB_low'] = bb.bollinger_lband()
        df['BB_mid'] = bb.bollinger_mavg()
        df['BB_width'] = (df['BB_high'] - df['BB_low']) / df['BB_mid']
        df['BB_position'] = (df['close'] - df['BB_low']) / (df['BB_high'] - df['BB_low'])
        
        # Moving Averages
        df['SMA_20'] = ta.trend.SMAIndicator(df['close'], window=20).sma_indicator()
        df['SMA_50'] = ta.trend.SMAIndicator(df['close'], window=50).sma_indicator()
        df['SMA_200'] = ta.trend.SMAIndicator(df['close'], window=200).sma_indicator()
        df['EMA_12'] = ta.trend.EMAIndicator(df['close'], window=12).ema_indicator()
        df['EMA_26'] = ta.trend.EMAIndicator(df['close'], window=26).ema_indicator()
        
        # ADX (Average Directional Index)
        adx = ta.trend.ADXIndicator(df['high'], df['low'], df['close'])
        df['ADX'] = adx.adx()
        df['ADX_pos'] = adx.adx_pos()
        df['ADX_neg'] = adx.adx_neg()
        
        # ATR (Average True Range)
        df['ATR'] = ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close']
        ).average_true_range()
        
        # OBV (On-Balance Volume)
        df['OBV'] = ta.volume.OnBalanceVolumeIndicator(df['close'], df['volume']).on_balance_volume()
        
        # Stochastic Oscillator
        stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
        df['Stoch'] = stoch.stoch()
        df['Stoch_signal'] = stoch.stoch_signal()
        
        # CCI (Commodity Channel Index)
        df['CCI'] = ta.trend.CCIIndicator(df['high'], df['low'], df['close']).cci()
        
        # Volume indicators
        df['Volume_SMA'] = df['volume'].rolling(window=20).mean()
        df['Volume_ratio'] = df['volume'] / df['Volume_SMA']
        
        # Price change features
        df['Price_change'] = df['close'].pct_change()
        df['Price_change_5'] = df['close'].pct_change(5)
        df['Price_change_20'] = df['close'].pct_change(20)
        
        # Volatility
        df['Volatility'] = df['Price_change'].rolling(window=20).std()
        
        # High-Low spread
        df['HL_spread'] = (df['high'] - df['low']) / df['close']
        
        # Support/Resistance levels (simplified)
        df['Resistance'] = df['high'].rolling(window=20).max()
        df['Support'] = df['low'].rolling(window=20).min()
        
        return df
    
    @staticmethod
    def add_custom_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Add custom trading indicators."""
        df = df.copy()
        
        # Price position in range
        df['Price_position'] = (df['close'] - df['low'].rolling(14).min()) / (
            df['high'].rolling(14).max() - df['low'].rolling(14).min()
        )
        
        # Volume-price trend
        df['VPT'] = (df['volume'] * df['Price_change']).cumsum()
        
        # Money Flow Index
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']
        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(14).sum()
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(14).sum()
        mfi_ratio = positive_flow / negative_flow.replace(0, np.nan)
        df['MFI'] = 100 - (100 / (1 + mfi_ratio))
        
        return df

