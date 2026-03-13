"""Helper functions for the trading AI system."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import yaml
from pathlib import Path


def load_config(config_path: str = "config/config.yaml") -> Dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def calculate_risk_reward_ratio(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    is_long: bool = True
) -> float:
    """
    Calculate risk to reward ratio.
    
    Args:
        entry_price: Entry price
        stop_loss: Stop loss price
        take_profit: Take profit price
        is_long: True for long position, False for short
    
    Returns:
        Risk to reward ratio (risk/reward)
    """
    if is_long:
        risk = entry_price - stop_loss
        reward = take_profit - entry_price
    else:
        risk = stop_loss - entry_price
        reward = entry_price - take_profit
    
    if reward == 0:
        return float('inf')
    
    return risk / reward


def calculate_position_size(
    account_balance: float,
    entry_price: float,
    stop_loss: float,
    risk_per_trade: float = 0.02,
    max_position_pct: float = 0.1
) -> float:
    """
    Calculate position size based on risk management.
    
    Args:
        account_balance: Total account balance
        entry_price: Entry price
        stop_loss: Stop loss price
        risk_per_trade: Percentage of balance to risk per trade
        max_position_pct: Maximum position size as percentage of balance
    
    Returns:
        Position size in base currency
    """
    risk_amount = account_balance * risk_per_trade
    price_risk = abs(entry_price - stop_loss)
    
    if price_risk == 0:
        return 0
    
    position_size = risk_amount / price_risk
    max_position = account_balance * max_position_pct
    
    return min(position_size, max_position)


def calculate_liquidation_price(
    entry_price: float,
    leverage: float,
    is_long: bool = True,
    margin_type: str = "isolated"
) -> float:
    """
    Calculate liquidation price for futures trading.
    
    Args:
        entry_price: Entry price
        leverage: Leverage used
        is_long: True for long position, False for short
        margin_type: "isolated" or "cross"
    
    Returns:
        Liquidation price
    """
    if is_long:
        liquidation_price = entry_price * (1 - 1/leverage)
    else:
        liquidation_price = entry_price * (1 + 1/leverage)
    
    return liquidation_price


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def normalize_features(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Normalize specified columns in dataframe."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            mean = df[col].mean()
            std = df[col].std()
            if std != 0:
                df[col] = (df[col] - mean) / std
    return df


def create_time_features(df: pd.DataFrame, time_col: str = 'timestamp') -> pd.DataFrame:
    """Create time-based features from timestamp."""
    df = df.copy()
    if time_col in df.columns:
        df[time_col] = pd.to_datetime(df[time_col])
        df['hour'] = df[time_col].dt.hour
        df['day_of_week'] = df[time_col].dt.dayofweek
        df['day_of_month'] = df[time_col].dt.day
        df['month'] = df[time_col].dt.month
    return df


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Calculate Sharpe ratio."""
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    excess_returns = returns - risk_free_rate
    return excess_returns.mean() / returns.std() * np.sqrt(252)  # Annualized


def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """Calculate maximum drawdown."""
    cumulative = equity_curve.cumsum()
    running_max = cumulative.expanding().max()
    drawdown = cumulative - running_max
    return abs(drawdown.min())

