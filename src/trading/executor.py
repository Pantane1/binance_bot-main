"""Order execution and position management."""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from utils.logger import setup_logger
from data_collection.binance_client import BinanceClient
from trading.risk_manager import RiskManager
from db.models import Position, Trade

logger = setup_logger(__name__)


class TradeExecutor:
    """Execute trades and manage positions."""
    
    def __init__(
        self,
        binance_client: BinanceClient,
        risk_manager: RiskManager,
        db_session_factory: Optional[sessionmaker] = None,
    ):
        """
        Initialize trade executor.
        
        Args:
            binance_client: Binance client instance
            risk_manager: RiskManager instance
            db_session_factory: Optional SQLAlchemy sessionmaker for persistence.
        """
        self.client = binance_client
        self.risk_manager = risk_manager
        self.active_positions: Dict[str, Dict] = {}
        self._session_factory = db_session_factory
    
    def execute_signal(self, signal: Dict) -> Optional[Dict]:
        """
        Execute a trading signal.
        
        Args:
            signal: Trading signal dictionary
        
        Returns:
            Order result dictionary or None if failed
        """
        try:
            symbol = signal['symbol']
            direction = signal['direction']
            position_size = signal['position_size']
            entry_price = signal['entry_price']
            futures = signal.get('futures', False)
            leverage = signal.get('leverage', 1)

            # Determine order side
            side = 'BUY' if direction == 'LONG' else 'SELL'

            # Quantize quantity to match Binance lot-size precision
            quantity = self.client.quantize_quantity(symbol, position_size, futures=futures)

            if quantity <= 0:
                logger.error(
                    f"Calculated quantity {quantity} is invalid after quantization "
                    f"for {symbol}; skipping order"
                )
                return None

            # Place market order to open position
            order = self.client.place_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=quantity,
                futures=futures,
                leverage=leverage
            )
            
            if not order:
                logger.error("Order execution failed")
                return None
            
            # Get partial TP levels from risk manager
            partial_tps = self.risk_manager.get_partial_take_profit_levels(
                entry_price,
                signal['stop_loss'],
                direction
            )
            
            # Place TP orders immediately (visible on Binance)
            tp_order_ids = []
            tp_close_side = 'SELL' if direction == 'LONG' else 'BUY'
            
            for tp_level in partial_tps:
                tp_price = tp_level['price']
                tp_fraction = tp_level['fraction']
                tp_quantity = quantity * tp_fraction
                tp_quantity = self.client.quantize_quantity(symbol, tp_quantity, futures=futures)
                
                if tp_quantity > 0:
                    try:
                        tp_order = self.client.place_take_profit_order(
                            symbol=symbol,
                            side=tp_close_side,
                            quantity=tp_quantity,
                            stop_price=tp_price,
                            futures=futures,
                            reduce_only=True
                        )
                        if tp_order:
                            tp_order_ids.append({
                                'order_id': tp_order.get('orderId'),
                                'price': tp_price,
                                'quantity': tp_quantity,
                                'fraction': tp_fraction,
                                'rr_multiple': tp_level['rr_multiple'],
                                'filled': False
                            })
                            logger.info(
                                f"TP order placed: {tp_fraction*100:.0f}% ({tp_quantity:.4f}) @ {tp_price:.2f} "
                                f"({tp_level['rr_multiple']}R) - Order ID: {tp_order.get('orderId')}"
                            )
                    except Exception as e:
                        logger.error(f"Failed to place TP order at {tp_price:.2f}: {e}")
            
            # Place stop loss order (visible on Binance)
            sl_order_id = None
            sl_price = signal['stop_loss']
            try:
                sl_order = self.client.place_stop_loss_order(
                    symbol=symbol,
                    side=tp_close_side,
                    quantity=quantity,  # Full position size for SL
                    stop_price=sl_price,
                    futures=futures,
                    reduce_only=True
                )
                if sl_order:
                    sl_order_id = sl_order.get('orderId')
                    logger.info(
                        f"Stop loss order placed: {quantity:.4f} @ {sl_price:.2f} - Order ID: {sl_order_id}"
                    )
            except Exception as e:
                logger.error(f"Failed to place stop loss order at {sl_price:.2f}: {e}")
            
            # Build in-memory position snapshot
            position = {
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'stop_loss': signal['stop_loss'],
                'take_profit': signal['take_profit'],
                'position_size': quantity,
                'remaining_size': quantity,  # Track remaining size for partial exits
                'leverage': leverage,
                'futures': futures,
                'order_id': order.get('orderId'),
                'sl_order_id': sl_order_id,  # Store SL order ID
                'tp_orders': tp_order_ids,  # Store TP order IDs
                'entry_time': datetime.now(),
                'highest_favorable_price': entry_price  # Track for trailing stop
            }

            db_position_id = None
            # Persist to DB if configured
            if self._session_factory is not None:
                session: Session = self._session_factory()
                try:
                    db_pos = Position(
                        symbol=symbol,
                        is_futures=futures,
                        direction=direction,
                        entry_price=entry_price,
                        stop_loss=signal['stop_loss'],
                        take_profit=signal['take_profit'],
                        size=quantity,
                        leverage=leverage,
                        opened_at=datetime.utcnow(),
                        status="OPEN",
                    )
                    session.add(db_pos)

                    # Also record a trade row
                    db_trade = Trade(
                        position=db_pos,
                        symbol=symbol,
                        side=side,
                        price=float(order.get('avgPrice', entry_price) or entry_price),
                        qty=quantity,
                        notional=float(order.get('cumQuote', 0) or 0),
                        fee=None,
                        is_futures=futures,
                        exchange_order_id=str(order.get('orderId')),
                    )
                    session.add(db_trade)

                    session.commit()
                    db_position_id = db_pos.id
                except Exception as e:
                    session.rollback()
                    logger.error(f"Error persisting position/trade to DB: {e}")
                finally:
                    session.close()

            if db_position_id is not None:
                position['position_id'] = db_position_id
            else:
                # Use timestamp as fallback unique ID
                position['position_id'] = int(datetime.now().timestamp() * 1000)

            # Use position_id in key to allow multiple positions per symbol/direction
            position_key = f"{symbol}_{direction}_{futures}_{position['position_id']}"
            self.active_positions[position_key] = position
            
            # Format TP orders list for logging
            tp_orders_str = ', '.join([
                f"{tp['fraction']*100:.0f}% @ {tp['price']:.2f}"
                for tp in tp_order_ids
            ])
            
            logger.info(
                f"Position opened with {len(tp_order_ids)} TP orders + 1 SL order: "
                f"{symbol} {direction} | Size: {quantity} | "
                f"TP orders: [{tp_orders_str}] | SL: {sl_price:.2f}"
            )
            
            return {
                'success': True,
                'order': order,
                'position': position,
                'tp_orders': tp_order_ids,
                'sl_order_id': sl_order_id
            }
                
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return None
    
    def place_stop_loss_order(
        self,
        position: Dict,
        stop_loss_price: float
    ) -> Optional[Dict]:
        """
        Place stop loss order.
        
        Args:
            position: Position dictionary
            stop_loss_price: Stop loss price
        
        Returns:
            Order result or None
        """
        try:
            symbol = position['symbol']
            direction = position['direction']
            futures = position.get('futures', False)
            
            # For stop loss, we'd typically use STOP_MARKET or STOP_LIMIT
            # This is a simplified version
            side = 'SELL' if direction == 'LONG' else 'BUY'
            
            # Note: Actual stop loss implementation would use stop order types
            # This is a placeholder for the logic
            logger.info(f"Stop loss order placed for {symbol} at {stop_loss_price}")
            
            return {'success': True, 'stop_loss_price': stop_loss_price}
            
        except Exception as e:
            logger.error(f"Error placing stop loss: {e}")
            return None
    
    def close_position(
        self,
        position: Dict,
        reason: str = "Manual close"
    ) -> Optional[Dict]:
        """
        Close an open position (fully or partially).
        
        Note: If TP/SL orders are placed on exchange, they will execute automatically.
        This method is for manual closes or when exchange orders need to be cancelled.
        
        Args:
            position: Position dictionary
            reason: Reason for closing (can indicate "PARTIAL_TP_XR_Y" for partial exits)
        
        Returns:
            Close order result or None
        """
        try:
            symbol = position['symbol']
            direction = position['direction']
            remaining_size = position.get('remaining_size', position.get('position_size', 0))
            futures = position.get('futures', False)
            position_id = position.get('position_id')
            
            # If manually closing (not via exchange TP/SL), cancel remaining exchange orders
            if reason not in ["Take profit hit", "Stop loss hit"] and "PARTIAL_TP_" not in reason:
                # Cancel remaining TP orders if manually closing
                tp_orders = position.get('tp_orders', [])
                for tp_order in tp_orders:
                    if not tp_order.get('filled', False):
                        order_id = tp_order.get('order_id')
                        if order_id:
                            try:
                                self.client.cancel_order(symbol, order_id, futures=futures)
                                logger.info(f"Cancelled TP order {order_id} for manual close")
                            except:
                                pass
                
                # Cancel SL order if manually closing
                sl_order_id = position.get('sl_order_id')
                if sl_order_id:
                    try:
                        self.client.cancel_order(symbol, sl_order_id, futures=futures)
                        logger.info(f"Cancelled SL order {sl_order_id} for manual close")
                    except:
                        pass
            
            # Check if this is a partial exit
            is_partial = reason.startswith("PARTIAL_TP_")
            if is_partial:
                # Parse fraction from reason (e.g., "PARTIAL_TP_1.0R_0.5")
                try:
                    parts = reason.split('_')
                    fraction = float(parts[-1])  # Last part is fraction
                    close_size = remaining_size * fraction
                    close_size = self.client.quantize_quantity(symbol, close_size, futures=futures)
                except:
                    logger.error(f"Could not parse partial exit fraction from reason: {reason}")
                    return None
            else:
                # Full close
                close_size = remaining_size
            
            if close_size <= 0:
                logger.warning(f"Invalid close size {close_size} for {symbol}")
                return None
            
            # Opposite side to close
            side = 'SELL' if direction == 'LONG' else 'BUY'
            
            order = self.client.place_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=close_size,
                futures=futures
            )
            
            if order:
                # Update position or remove it
                position_key = f"{symbol}_{direction}_{futures}_{position_id}"
                
                if is_partial:
                    # Update remaining size and mark TP level as taken
                    position['remaining_size'] = remaining_size - close_size
                    # Parse and mark TP level
                    try:
                        parts = reason.split('_')
                        rr_multiple = parts[2].replace('R', '')  # e.g., "1.0R" -> "1.0"
                        tp_key = f"tp_{rr_multiple}_taken"
                        position[tp_key] = True
                    except:
                        pass
                    
                    logger.info(
                        f"Partial exit: {close_size:.4f} of {symbol} {direction} "
                        f"at {reason} (remaining: {position['remaining_size']:.4f})"
                    )
                else:
                    # Full close - remove from active positions
                    if position_key in self.active_positions:
                        del self.active_positions[position_key]

                # Persist close + realized PnL if DB is configured
                if self._session_factory is not None and position_id:
                    session: Session = self._session_factory()
                    try:
                        db_pos = session.get(Position, position_id)
                        if db_pos is not None:
                            if is_partial:
                                # Update size for partial exit
                                db_pos.size = position['remaining_size']
                            else:
                                # Full close
                                if db_pos.status == "OPEN":
                                    db_pos.closed_at = datetime.utcnow()
                                    db_pos.status = "CLOSED"
                            
                            # Record closing trade
                            db_trade = Trade(
                                position_id=position_id,
                                symbol=symbol,
                                side=side,
                                price=float(order.get('avgPrice', db_pos.entry_price if db_pos else 0) or 0),
                                qty=close_size,
                                notional=float(order.get('cumQuote', 0) or 0),
                                is_futures=futures,
                                exchange_order_id=str(order.get('orderId')),
                            )
                            session.add(db_trade)
                            session.commit()
                    except Exception as e:
                        session.rollback()
                        logger.error(f"Error updating position/trade in DB: {e}")
                    finally:
                        session.close()
                
                logger.info(f"Position closed: {symbol} {direction} - {reason}")
                return {'success': True, 'order': order, 'reason': reason}
            else:
                logger.error("Failed to close position")
                return None
                
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return None
    
    def get_active_positions(self) -> List[Dict]:
        """Get list of active positions."""
        return list(self.active_positions.values())
    
    def update_positions(self):
        """Sync active_positions (and DB, if configured) with exchange futures positions.

        This is primarily used on reconnect/startup to reconstruct open positions
        so that SL/TP and exit logic can manage them.
        """
        try:
            futures_positions = self.client.get_positions(futures=True)

            for pos in futures_positions:
                amt = float(pos.get("positionAmt", 0))
                if amt == 0:
                    continue

                symbol = pos.get("symbol")
                entry_price = float(pos.get("entryPrice", 0))
                leverage = int(float(pos.get("leverage", 1)))
                direction = "LONG" if amt > 0 else "SHORT"
                size = abs(amt)

                # Compute fresh SL/TP using the risk manager
                stop_loss, take_profit = self.risk_manager.calculate_stop_loss_take_profit(
                    entry_price,
                    direction,
                )

                position_key = f"{symbol}_{direction}_True"
                position = {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "position_size": size,
                    "remaining_size": size,  # Track remaining for partial exits
                    "leverage": leverage,
                    "futures": True,
                    "order_id": None,
                    "entry_time": datetime.utcnow(),
                    "highest_favorable_price": entry_price  # Track for trailing stop
                }

                # Optionally persist to DB if not already present
                if self._session_factory is not None:
                    session: Session = self._session_factory()
                    try:
                        # Try to find an open position with same symbol/direction/size
                        db_pos = (
                            session.query(Position)
                            .filter(
                                Position.symbol == symbol,
                                Position.is_futures == True,
                                Position.direction == direction,
                                Position.status == "OPEN",
                            )
                            .order_by(Position.opened_at.desc())
                            .first()
                        )
                        if db_pos is None:
                            db_pos = Position(
                                symbol=symbol,
                                is_futures=True,
                                direction=direction,
                                entry_price=entry_price,
                                stop_loss=stop_loss,
                                take_profit=take_profit,
                                size=size,
                                leverage=leverage,
                                opened_at=datetime.utcnow(),
                                status="OPEN",
                            )
                            session.add(db_pos)
                            session.commit()
                        position["position_id"] = db_pos.id
                    except Exception as e:
                        session.rollback()
                        logger.error(f"Error syncing positions to DB: {e}")
                    finally:
                        session.close()
                else:
                    # Fallback ID if no DB
                    position["position_id"] = int(datetime.utcnow().timestamp() * 1000)

                # Use position_id in key to allow multiple positions
                position_key = f"{symbol}_{direction}_True_{position['position_id']}"
                self.active_positions[position_key] = position

            logger.debug("Positions synced from exchange")

        except Exception as e:
            logger.error(f"Error updating positions: {e}")
    
    def update_stop_loss_order(
        self,
        position: Dict,
        new_stop_loss: float
    ) -> bool:
        """
        Update stop loss order on exchange when trailing stop moves.
        
        This cancels the old SL order and places a new one at the updated price.
        
        Args:
            position: Position dictionary
            new_stop_loss: New stop loss price (from trailing stop)
        
        Returns:
            True if order was successfully updated, False otherwise
        """
        try:
            symbol = position['symbol']
            direction = position['direction']
            futures = position.get('futures', False)
            sl_order_id = position.get('sl_order_id')
            remaining_size = position.get('remaining_size', position.get('position_size', 0))
            
            if not sl_order_id:
                logger.debug(f"No SL order ID for {symbol}, cannot update")
                return False
            
            # Check if order still exists and is open
            try:
                order_status = self.client.get_order(symbol, sl_order_id, futures=futures)
                if order_status.get('status') in ['FILLED', 'CANCELED', 'EXPIRED']:
                    logger.debug(f"SL order {sl_order_id} already {order_status.get('status')}, cannot update")
                    return False
            except Exception as e:
                logger.debug(f"Could not check SL order {sl_order_id} status: {e}")
                # Continue anyway - try to cancel and replace
            
            # Cancel old SL order
            try:
                self.client.cancel_order(symbol, sl_order_id, futures=futures)
                logger.info(f"Cancelled old SL order {sl_order_id} for {symbol}")
            except Exception as e:
                logger.warning(f"Could not cancel old SL order {sl_order_id}: {e}")
                # Continue anyway - try to place new one
            
            # Place new SL order at updated price
            sl_close_side = 'SELL' if direction == 'LONG' else 'BUY'
            try:
                new_sl_order = self.client.place_stop_loss_order(
                    symbol=symbol,
                    side=sl_close_side,
                    quantity=remaining_size,  # Use remaining size (may have partial exits)
                    stop_price=new_stop_loss,
                    futures=futures,
                    reduce_only=True
                )
                
                if new_sl_order:
                    position['sl_order_id'] = new_sl_order.get('orderId')
                    position['stop_loss'] = new_stop_loss
                    logger.info(
                        f"Updated SL order for {symbol}: {new_stop_loss:.2f} "
                        f"(Order ID: {new_sl_order.get('orderId')})"
                    )
                    return True
            except Exception as e:
                logger.error(f"Failed to place new SL order for {symbol} at {new_stop_loss:.2f}: {e}")
                return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating stop loss order: {e}")
            return False

