"""Risk management for trading positions."""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from datetime import datetime
from utils.logger import setup_logger
from utils.helpers import (
    calculate_risk_reward_ratio,
    calculate_position_size,
    calculate_liquidation_price
)

logger = setup_logger(__name__)


class RiskManager:
    """Manage risk for trading positions."""
    
    def __init__(self, config: Dict, executor=None):
        """
        Initialize risk manager.
        
        Args:
            config: Risk management configuration
            executor: Optional TradeExecutor instance (set after initialization)
        """
        self.config = config
        self.risk_config = config.get('risk', {})
        self.position_config = config.get('position_sizing', {})
        self.executor = executor
        
        # Daily tracking
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_reset_date = datetime.now().date()
    
    def reset_daily_stats(self):
        """Reset daily statistics."""
        current_date = datetime.now().date()
        if current_date > self.last_reset_date:
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.last_reset_date = current_date
            logger.info("Daily statistics reset")
    
    def check_daily_loss_limit(self, account_balance: float) -> bool:
        """
        Check if daily loss limit has been reached.
        
        Args:
            account_balance: Current account balance
        
        Returns:
            True if can trade, False if limit reached
        """
        self.reset_daily_stats()
        
        max_daily_loss = self.risk_config.get('max_daily_loss', 0.05)
        max_loss_amount = account_balance * max_daily_loss
        
        if self.daily_pnl <= -max_loss_amount:
            logger.warning(f"Daily loss limit reached: {self.daily_pnl:.2f}")
            return False
        
        return True
    
    def calculate_stop_loss_take_profit(
        self,
        entry_price: float,
        direction: str,
        risk_reward_ratio: float = None
    ) -> Tuple[float, float]:
        """
        Calculate stop loss and take profit levels.
        
        Args:
            entry_price: Entry price
            direction: 'LONG' or 'SHORT'
            risk_reward_ratio: Desired risk to reward ratio (default from config)
        
        Returns:
            Tuple of (stop_loss, take_profit)
        """
        if risk_reward_ratio is None:
            risk_reward_ratio = self.risk_config.get('risk_reward_ratio', 0.5)
        
        stop_loss_pct = self.risk_config.get('stop_loss_pct', 0.015)
        # Use explicit TP if set, otherwise calculate from R:R
        take_profit_pct = self.risk_config.get('take_profit_pct')
        if take_profit_pct is None:
            take_profit_pct = stop_loss_pct / risk_reward_ratio
        
        is_long = direction == 'LONG'
        
        if is_long:
            stop_loss = entry_price * (1 - stop_loss_pct)
            take_profit = entry_price * (1 + take_profit_pct)
        else:
            stop_loss = entry_price * (1 + stop_loss_pct)
            take_profit = entry_price * (1 - take_profit_pct)
        
        return stop_loss, take_profit
    
    def get_partial_take_profit_levels(
        self,
        entry_price: float,
        stop_loss: float,
        direction: str
    ) -> List[Dict]:
        """
        Get partial take profit levels based on R multiples.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            direction: 'LONG' or 'SHORT'
        
        Returns:
            List of partial TP levels with fraction and price
        """
        partial_tps = self.risk_config.get('partial_take_profits', [])
        if not partial_tps:
            return []
        
        # Calculate 1R distance
        if direction == 'LONG':
            r_distance = entry_price - stop_loss
        else:
            r_distance = stop_loss - entry_price
        
        levels = []
        for tp_config in partial_tps:
            rr_multiple = tp_config.get('rr_multiple', 1.0)
            fraction = tp_config.get('fraction', 0.5)
            
            if direction == 'LONG':
                tp_price = entry_price + (r_distance * rr_multiple)
            else:
                tp_price = entry_price - (r_distance * rr_multiple)
            
            levels.append({
                'fraction': fraction,
                'rr_multiple': rr_multiple,
                'price': tp_price
            })
        
        return levels
    
    def calculate_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        stop_loss: float,
        direction: str,
        highest_favorable_price: float = None
    ) -> float:
        """
        Calculate trailing stop loss price.
        
        Args:
            entry_price: Original entry price
            current_price: Current market price
            stop_loss: Original stop loss
            direction: 'LONG' or 'SHORT'
            highest_favorable_price: Highest price reached in favor (for LONG) or lowest (for SHORT)
        
        Returns:
            Updated trailing stop loss price
        """
        trailing_config = self.risk_config.get('trailing_stop', {})
        if not trailing_config.get('enabled', False):
            return stop_loss
        
        activate_rr = trailing_config.get('activate_rr', 1.0)
        trail_pct = trailing_config.get('trail_pct', 0.01)
        
        # Calculate 1R distance
        if direction == 'LONG':
            r_distance = entry_price - stop_loss
            profit_target = entry_price + (r_distance * activate_rr)
            
            # Only activate if price has reached profit target
            if current_price < profit_target:
                return stop_loss
            
            # Use highest price reached
            peak_price = highest_favorable_price if highest_favorable_price else current_price
            new_stop = peak_price * (1 - trail_pct)
            return max(new_stop, stop_loss)  # Never move stop loss against us
        else:  # SHORT
            r_distance = stop_loss - entry_price
            profit_target = entry_price - (r_distance * activate_rr)
            
            # Only activate if price has reached profit target
            if current_price > profit_target:
                return stop_loss
            
            # Use lowest price reached
            trough_price = highest_favorable_price if highest_favorable_price else current_price
            new_stop = trough_price * (1 + trail_pct)
            return min(new_stop, stop_loss)  # Never move stop loss against us
    
    def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float,
        leverage: int = 1
    ) -> float:
        """
        Calculate position size based on risk management.
        
        Args:
            account_balance: Account balance
            entry_price: Entry price
            stop_loss: Stop loss price
            leverage: Leverage for futures (1 for spot)
        
        Returns:
            Position size in base currency
        """
        risk_per_trade = self.risk_config.get('risk_per_trade', 0.02)
        max_position_pct = self.risk_config.get('max_position_size', 0.1)
        
        # Adjust for leverage (futures)
        if leverage > 1:
            # For futures, position size is based on notional value
            position_size = calculate_position_size(
                account_balance * leverage,  # Adjusted balance for leverage
                entry_price,
                stop_loss,
                risk_per_trade,
                max_position_pct
            )
        else:
            # Spot trading
            position_size = calculate_position_size(
                account_balance,
                entry_price,
                stop_loss,
                risk_per_trade,
                max_position_pct
            )
        
        return position_size
    
    def validate_trade(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        direction: str,
        account_balance: float,
        leverage: int = 1
    ) -> Tuple[bool, str]:
        """
        Validate if a trade meets risk criteria.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            direction: 'LONG' or 'SHORT'
            account_balance: Account balance
            leverage: Leverage for futures
        
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check daily loss limit
        if not self.check_daily_loss_limit(account_balance):
            return False, "Daily loss limit reached"
        
        # Calculate risk to reward ratio
        rr_ratio = calculate_risk_reward_ratio(
            entry_price,
            stop_loss,
            take_profit,
            is_long=(direction == 'LONG')
        )
        
        # Check if meets minimum risk/reward requirement
        max_rr_ratio = self.risk_config.get('risk_reward_ratio', 0.33)
        if rr_ratio > max_rr_ratio:
            return False, f"Risk/reward ratio {rr_ratio:.2f} exceeds maximum {max_rr_ratio:.2f}"
        
        # Check leverage limits
        max_leverage = self.risk_config.get('max_leverage', 3)
        if leverage > max_leverage:
            return False, f"Leverage {leverage} exceeds maximum {max_leverage}"
        
        # Check liquidation buffer for futures
        if leverage > 1:
            liquidation_price = calculate_liquidation_price(
                entry_price,
                leverage,
                is_long=(direction == 'LONG')
            )
            
            liquidation_buffer = self.risk_config.get('liquidation_buffer', 0.10)
            
            if direction == 'LONG':
                distance_to_liquidation = (entry_price - liquidation_price) / entry_price
            else:
                distance_to_liquidation = (liquidation_price - entry_price) / entry_price
            
            if distance_to_liquidation < liquidation_buffer:
                return False, f"Liquidation buffer {distance_to_liquidation:.2%} below minimum {liquidation_buffer:.2%}"
        
        return True, "Trade validated"
    
    def calculate_liquidation_safety(
        self,
        entry_price: float,
        leverage: int,
        direction: str,
        current_price: float
    ) -> Dict:
        """
        Calculate liquidation safety metrics.
        
        Args:
            entry_price: Entry price
            leverage: Leverage used
            direction: 'LONG' or 'SHORT'
            current_price: Current market price
        
        Returns:
            Dictionary with safety metrics
        """
        liquidation_price = calculate_liquidation_price(
            entry_price,
            leverage,
            is_long=(direction == 'LONG')
        )
        
        if direction == 'LONG':
            distance_pct = (current_price - liquidation_price) / current_price
            price_change_to_liquidation = (liquidation_price - current_price) / current_price
        else:
            distance_pct = (liquidation_price - current_price) / current_price
            price_change_to_liquidation = (current_price - liquidation_price) / current_price
        
        liquidation_buffer = self.risk_config.get('liquidation_buffer', 0.10)
        is_safe = distance_pct >= liquidation_buffer
        
        return {
            'liquidation_price': liquidation_price,
            'distance_pct': distance_pct,
            'price_change_to_liquidation': price_change_to_liquidation,
            'is_safe': is_safe,
            'buffer_required': liquidation_buffer
        }
    
    def update_daily_stats(self, pnl: float):
        """Update daily P&L and trade count."""
        self.daily_pnl += pnl
        self.daily_trades += 1
        logger.info(f"Daily P&L: {self.daily_pnl:.2f}, Trades: {self.daily_trades}")

