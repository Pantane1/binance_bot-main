"""Trading strategy implementation."""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from utils.logger import setup_logger
from trading.risk_manager import RiskManager
from models.predictors import PricePredictor

logger = setup_logger(__name__)


class TradingStrategy:
    """Main trading strategy that combines predictions with risk management."""
    
    def __init__(
        self,
        predictor: PricePredictor,
        risk_manager: RiskManager,
        config: Dict
    ):
        """
        Initialize trading strategy.
        
        Args:
            predictor: PricePredictor instance
            risk_manager: RiskManager instance
            config: Trading configuration
        """
        self.predictor = predictor
        self.risk_manager = risk_manager
        self.config = config
        self.trading_config = config.get('trading', {})
        # Make executor accessible for position checks
        if hasattr(risk_manager, 'executor'):
            self.executor = risk_manager.executor
        else:
            self.executor = None
    
    def generate_signal(
        self,
        features: pd.DataFrame,
        current_price: float,
        account_balance: float,
        symbol: str,
        futures: bool = False
    ) -> Optional[Dict]:
        """
        Generate trading signal based on prediction and risk management.
        
        Args:
            features: Feature dataframe
            current_price: Current market price
            account_balance: Account balance
            symbol: Trading pair symbol
            futures: Use futures trading
        
        Returns:
            Trading signal dictionary or None if no signal
        """
        try:
            # Get prediction first
            prediction = self.predictor.predict(features, current_price)
            
            # Check if prediction is confident enough
            confidence = prediction.get('confidence', 0.0)
            threshold = self.predictor.confidence_threshold
            if not prediction.get('is_confident', False):
                logger.info(
                    f"Prediction confidence too low: {confidence:.3f} < {threshold:.3f} "
                    f"(threshold). Models disagree or market conditions uncertain. "
                    f"Predicted: {prediction.get('direction', 'HOLD')} "
                    f"{prediction.get('predicted_return', 0)*100:.2f}%"
                )
                return None
            
            # Check minimum prediction strength (filters weak signals)
            predicted_return = abs(prediction.get('predicted_return', 0))
            min_strength = self.predictor.config.get('prediction', {}).get('min_prediction_strength', 0.0)
            if predicted_return < min_strength:
                logger.info(
                    f"Prediction strength too weak: {predicted_return*100:.2f}% < {min_strength*100:.2f}% "
                    f"(minimum). Signal not strong enough to enter."
                )
                return None
            
            direction = prediction['direction']
            if direction == 'HOLD':
                return None
            
            # Check max total positions across all symbols (global risk control)
            max_total_positions = self.trading_config.get('max_total_positions', 999)
            if self.executor:
                all_positions = self.executor.get_active_positions()
                if len(all_positions) >= max_total_positions:
                    logger.info(
                        f"Max total positions ({max_total_positions}) reached across all symbols, "
                        f"skipping new signal for {symbol}"
                    )
                    return None
            
            # Check max positions per symbol (after we know direction)
            max_positions = self.trading_config.get('max_positions_per_symbol', 1)
            allow_reentry = self.trading_config.get('allow_reentry_after_scaling', True)
            min_profit_before_reentry = self.trading_config.get('min_profit_before_reentry', 0.0)
            
            if self.executor:
                open_positions = self.executor.get_active_positions()
                matching_positions = [
                    p for p in open_positions
                    if p['symbol'] == symbol and p['direction'] == direction and p.get('futures') == futures
                ]
                
                if allow_reentry:
                    # Count only "full" positions (not scaled-out positions with small remaining_size)
                    # Allow re-entry if existing positions are mostly scaled out
                    active_positions = [
                        p for p in matching_positions
                        if p.get('remaining_size', p.get('position_size', 0)) > p.get('position_size', 1) * 0.3
                    ]
                    
                    if len(active_positions) >= max_positions:
                        logger.info(
                            f"Max active positions ({max_positions}) reached for {symbol} {direction} "
                            f"({'futures' if futures else 'spot'}), skipping new signal"
                        )
                        return None
                    
                    # If we have scaled-out positions, allow re-entry for better entries
                    scaled_out_positions = [
                        p for p in matching_positions
                        if p.get('remaining_size', p.get('position_size', 0)) <= p.get('position_size', 1) * 0.3
                    ]
                    if scaled_out_positions and len(active_positions) < max_positions:
                        # Check if scaled-out positions have achieved minimum profit
                        if min_profit_before_reentry > 0:
                            entry_price = scaled_out_positions[0].get('entry_price', current_price)
                            if direction == 'LONG':
                                profit_pct = (current_price - entry_price) / entry_price
                            else:
                                profit_pct = (entry_price - current_price) / entry_price
                            
                            if profit_pct < min_profit_before_reentry:
                                logger.info(
                                    f"Re-entry blocked for {symbol} {direction} - "
                                    f"scaled-out position profit {profit_pct*100:.2f}% < "
                                    f"minimum {min_profit_before_reentry*100:.2f}% required"
                                )
                                return None
                        
                        logger.info(
                            f"Allowing re-entry for {symbol} {direction} - "
                            f"existing position scaled out ({len(scaled_out_positions)} positions), "
                            f"signal still strong (confidence: {prediction.get('confidence', 0):.2f})"
                        )
                else:
                    # Original behavior: count all positions
                    if len(matching_positions) >= max_positions:
                        logger.info(
                            f"Max positions ({max_positions}) reached for {symbol} {direction} "
                            f"({'futures' if futures else 'spot'}), skipping new signal"
                        )
                        return None
            
            # Calculate stop loss and take profit
            stop_loss, take_profit = self.risk_manager.calculate_stop_loss_take_profit(
                current_price,
                direction
            )
            
            # Get leverage
            leverage = 1 if not futures else self.risk_manager.risk_config.get('max_leverage', 3)
            
            # Validate trade
            is_valid, reason = self.risk_manager.validate_trade(
                current_price,
                stop_loss,
                take_profit,
                direction,
                account_balance,
                leverage
            )
            
            if not is_valid:
                logger.info(f"Trade validation failed: {reason}")
                return None
            
            # Calculate position size
            position_size = self.risk_manager.calculate_position_size(
                account_balance,
                current_price,
                stop_loss,
                leverage
            )
            
            # Calculate liquidation safety for futures
            liquidation_safety = None
            if futures and leverage > 1:
                liquidation_safety = self.risk_manager.calculate_liquidation_safety(
                    current_price,
                    leverage,
                    direction,
                    current_price
                )
            
            # Calculate risk/reward ratio
            rr_ratio = self.risk_manager.risk_config.get('risk_reward_ratio', 0.33)
            
            signal = {
                'symbol': symbol,
                'direction': direction,
                'entry_price': current_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_size': position_size,
                'leverage': leverage,
                'risk_reward_ratio': rr_ratio,
                'predicted_return': prediction['predicted_return'],
                'confidence': prediction['confidence'],
                'liquidation_safety': liquidation_safety,
                'futures': futures,
                'timestamp': datetime.now()
            }
            
            logger.info(
                f"Signal generated: {direction} {symbol} | "
                f"Entry: {current_price:.2f} | "
                f"SL: {stop_loss:.2f} | "
                f"TP: {take_profit:.2f} | "
                f"Size: {position_size:.4f} | "
                f"Leverage: {leverage}x"
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return None
    
    def should_exit_position(
        self,
        position: Dict,
        current_price: float,
        features: pd.DataFrame
    ) -> Tuple[bool, str]:
        """
        Determine if a position should be exited (fully or partially).
        
        Args:
            position: Current position dictionary
            current_price: Current market price
            features: Current feature dataframe
        
        Returns:
            Tuple of (should_exit, reason) - reason can indicate "PARTIAL" for partial exits
        """
        entry_price = position.get('entry_price', 0)
        stop_loss = position.get('stop_loss', 0)
        take_profit = position.get('take_profit', 0)
        direction = position.get('direction', 'LONG')
        remaining_size = position.get('remaining_size', position.get('position_size', 0))
        
        # Update trailing stop if enabled
        highest_favorable = position.get('highest_favorable_price')
        if direction == 'LONG':
            if highest_favorable is None or current_price > highest_favorable:
                position['highest_favorable_price'] = current_price
        else:  # SHORT
            if highest_favorable is None or current_price < highest_favorable:
                position['highest_favorable_price'] = current_price
        
        # Track scaled-out ratio for re-entry logic
        original_size = position.get('position_size', remaining_size)
        if original_size > 0:
            scaled_out_ratio = remaining_size / original_size
            position['scaled_out_ratio'] = scaled_out_ratio
        
        # Check if TP orders have been filled on exchange (exchange-side execution)
        if self.executor:
            tp_orders = position.get('tp_orders', [])
            for tp_order in tp_orders:
                if tp_order.get('filled', False):
                    continue  # Already processed
                
                order_id = tp_order.get('order_id')
                if order_id:
                    try:
                        order_status = self.executor.client.get_order(
                            symbol=position['symbol'],
                            order_id=order_id,
                            futures=position.get('futures', False)
                        )
                        if order_status.get('status') == 'FILLED':
                            # TP order filled - update position
                            filled_fraction = tp_order.get('fraction', 0)
                            current_remaining = position.get('remaining_size', position['position_size'])
                            position['remaining_size'] = current_remaining * (1 - filled_fraction)
                            tp_order['filled'] = True
                            logger.info(
                                f"TP order {order_id} filled on exchange: {filled_fraction*100:.0f}% "
                                f"({tp_order.get('quantity', 0):.4f}) @ {tp_order['price']:.2f} "
                                f"({tp_order.get('rr_multiple', 0)}R) | Remaining: {position['remaining_size']:.4f}"
                            )
                    except Exception as e:
                        # Order might not exist or already filled, or API error
                        logger.debug(f"Could not check TP order {order_id} status: {e}")
        
        # Calculate trailing stop
        trailing_stop = self.risk_manager.calculate_trailing_stop(
            entry_price,
            current_price,
            stop_loss,
            direction,
            position.get('highest_favorable_price')
        )
        
        # Update position's stop loss if trailing moved it
        if trailing_stop != stop_loss:
            old_stop = position['stop_loss']
            position['stop_loss'] = trailing_stop
            
            # Update SL order on exchange if executor is available
            if self.executor:
                # Only update if the change is significant (avoid excessive API calls)
                # Update if change is > 0.1% of entry price
                min_change_pct = 0.001
                change_pct = abs(trailing_stop - old_stop) / entry_price
                
                if change_pct >= min_change_pct:
                    success = self.executor.update_stop_loss_order(position, trailing_stop)
                    if success:
                        logger.info(
                            f"Trailing stop updated on exchange for {position.get('symbol')}: "
                            f"{old_stop:.2f} -> {trailing_stop:.2f} (Order ID: {position.get('sl_order_id')})"
                        )
                    else:
                        logger.debug(
                            f"Trailing stop updated in memory for {position.get('symbol')}: "
                            f"{old_stop:.2f} -> {trailing_stop:.2f} (Exchange update failed)"
                        )
                else:
                    logger.debug(
                        f"Trailing stop updated in memory for {position.get('symbol')}: "
                        f"{old_stop:.2f} -> {trailing_stop:.2f} (change too small: {change_pct*100:.3f}%)"
                    )
            else:
                logger.debug(f"Trailing stop updated for {position.get('symbol')}: {stop_loss:.2f} -> {trailing_stop:.2f}")
        
        # Check trailing stop loss
        if direction == 'LONG':
            if current_price <= trailing_stop:
                return True, "Trailing stop loss hit"
        else:  # SHORT
            if current_price >= trailing_stop:
                return True, "Trailing stop loss hit"
        
        # Check original stop loss (if trailing didn't activate)
        if direction == 'LONG':
            if current_price <= stop_loss:
                return True, "Stop loss hit"
        else:  # SHORT
            if current_price >= stop_loss:
                return True, "Stop loss hit"
        
        # Check partial take profits
        partial_tps = self.risk_manager.get_partial_take_profit_levels(
            entry_price,
            stop_loss,
            direction
        )
        
        for tp_level in partial_tps:
            tp_price = tp_level['price']
            fraction = tp_level['fraction']
            rr_multiple = tp_level['rr_multiple']
            
            # Check if we've hit this TP level and haven't taken it yet
            tp_key = f"tp_{rr_multiple}_taken"
            if position.get(tp_key, False):
                continue  # Already took this level
            
            if direction == 'LONG' and current_price >= tp_price:
                return True, f"PARTIAL_TP_{rr_multiple}R_{fraction}"
            elif direction == 'SHORT' and current_price <= tp_price:
                return True, f"PARTIAL_TP_{rr_multiple}R_{fraction}"
        
        # Check final take profit
        if direction == 'LONG':
            if current_price >= take_profit:
                return True, "Take profit hit"
        else:  # SHORT
            if current_price <= take_profit:
                return True, "Take profit hit"
        
        # Check if prediction has reversed
        try:
            prediction = self.predictor.predict(features, current_price)
            predicted_direction = prediction.get('direction', 'HOLD')
            
            if predicted_direction != direction and predicted_direction != 'HOLD':
                # Prediction reversed, consider exit
                if prediction.get('confidence', 0) > 0.7:
                    return True, "Prediction reversed with high confidence"
        except:
            pass
        
        # Check liquidation safety for futures
        if position.get('futures', False) and position.get('leverage', 1) > 1:
            liquidation_safety = self.risk_manager.calculate_liquidation_safety(
                entry_price,
                position.get('leverage', 1),
                direction,
                current_price
            )
            
            if not liquidation_safety.get('is_safe', True):
                return True, "Liquidation risk too high"
        
        return False, "Hold position"

