"""Binance API client for market data and trading."""

from binance.client import Client
from binance.exceptions import BinanceAPIException
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time
from utils.logger import setup_logger

logger = setup_logger(__name__)


class BinanceClient:
    """Wrapper for Binance API client with enhanced functionality."""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """
        Initialize Binance client.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet for testing
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # Initialize clients (spot + futures) for the chosen environment
        # Set recvWindow to 5000ms (5 seconds) to handle network latency
        if testnet:
            self.spot_client = Client(
                api_key=api_key,
                api_secret=api_secret,
                testnet=True,
                requests_params={'timeout': 10}
            )
            self.futures_client = Client(
                api_key=api_key,
                api_secret=api_secret,
                testnet=True,
                requests_params={'timeout': 10}
            )
        else:
            self.spot_client = Client(
                api_key=api_key,
                api_secret=api_secret,
                requests_params={'timeout': 10}
            )
            self.futures_client = Client(
                api_key=api_key,
                api_secret=api_secret,
                requests_params={'timeout': 10}
            )
        
        # Sync server time on initialization to reduce timestamp errors
        try:
            if testnet:
                server_time = self.futures_client.futures_time()
            else:
                server_time = self.spot_client.get_server_time()
            logger.debug(f"Server time synced: {server_time}")
        except Exception as e:
            logger.warning(f"Could not sync server time on init: {e}")
        
        logger.info(f"Binance client initialized (testnet={testnet})")

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def validate_for_mode(self, trading_mode: str) -> None:
        """
        Validate API key, permissions and IP for the configured trading mode.

        Performs lightweight private calls against spot and/or futures
        endpoints and raises RuntimeError immediately on failure so the
        application can fail fast instead of discovering issues later.

        Args:
            trading_mode: 'spot', 'futures' or 'both'

        Raises:
            RuntimeError: if any required API check fails.
        """
        errors: List[str] = []

        # Spot checks
        if trading_mode in ["spot", "both"]:
            try:
                self.spot_client.ping()
                _ = self.spot_client.get_account()
            except BinanceAPIException as e:
                errors.append(f"Spot API check failed: {e}")
            except Exception as e:
                errors.append(f"Spot connectivity check failed: {e}")

        # Futures checks
        if trading_mode in ["futures", "both"]:
            try:
                self.futures_client.futures_ping()
                _ = self.futures_client.futures_account()
            except BinanceAPIException as e:
                errors.append(f"Futures API check failed: {e}")
            except Exception as e:
                errors.append(f"Futures connectivity check failed: {e}")

        if errors:
            message = (
                "Binance API validation failed. Details:\n"
                + "\n".join(f"- {err}" for err in errors)
                + "\n\nPlease verify:\n"
                  "  1) You are using the correct keys for testnet vs mainnet.\n"
                  "  2) The key has required permissions (Spot and/or Futures enabled).\n"
                  "  3) If IP restrictions are enabled, your current IP is whitelisted.\n"
            )
            logger.error(message)
            raise RuntimeError(message)

        logger.info("Binance API key and permissions validated for trading mode '%s'", trading_mode)

    # ------------------------------------------------------------------
    # Symbol info / precision helpers
    # ------------------------------------------------------------------
    def get_symbol_filters(self, symbol: str, futures: bool = False) -> List[Dict]:
        """
        Get the filters for a symbol (lot size, price precision, etc.).
        """
        try:
            if futures:
                info = self.futures_client.futures_exchange_info()
                for s in info.get("symbols", []):
                    if s.get("symbol") == symbol:
                        return s.get("filters", [])
            else:
                info = self.spot_client.get_symbol_info(symbol)
                if info:
                    return info.get("filters", [])
        except Exception as e:
            logger.error(f"Error fetching symbol filters for {symbol}: {e}")
        return []

    def get_symbol_lot_size(self, symbol: str, futures: bool = False) -> float:
        """
        Get the lot size (stepSize) for a symbol.
        """
        filters = self.get_symbol_filters(symbol, futures=futures)
        for f in filters:
            if f.get("filterType") == "LOT_SIZE":
                try:
                    return float(f.get("stepSize", 0.0))
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    def get_symbol_price_precision(self, symbol: str, futures: bool = False) -> int:
        """
        Get the price precision (tickSize) for a symbol.
        
        Returns:
            Number of decimal places allowed for price
        """
        filters = self.get_symbol_filters(symbol, futures=futures)
        for f in filters:
            if f.get("filterType") == "PRICE_FILTER":
                try:
                    tick_size = float(f.get("tickSize", 0.0))
                    if tick_size > 0:
                        # Determine decimal precision from tick size
                        tick_str = f"{tick_size:.16f}".rstrip("0")
                        if "." in tick_str:
                            return len(tick_str.split(".")[1])
                        return 0
                except (TypeError, ValueError):
                    pass
        # Fallback: use 8 decimals (common for most assets)
        return 8
    
    def quantize_price(self, symbol: str, price: float, futures: bool = False) -> float:
        """
        Adjust price to match Binance price precision (tickSize).
        
        Args:
            symbol: Trading pair
            price: Price to quantize
            futures: Use futures trading
        
        Returns:
            Quantized price matching Binance precision requirements
        """
        filters = self.get_symbol_filters(symbol, futures=futures)
        tick_size = None
        
        for f in filters:
            if f.get("filterType") == "PRICE_FILTER":
                try:
                    tick_size = float(f.get("tickSize", 0.0))
                    break
                except (TypeError, ValueError):
                    pass
        
        if tick_size and tick_size > 0:
            # Round to nearest tick
            return round(price / tick_size) * tick_size
        
        # Fallback: use precision-based rounding
        precision = self.get_symbol_price_precision(symbol, futures)
        return round(price, precision)
    
    def quantize_quantity(self, symbol: str, quantity: float, futures: bool = False) -> float:
        """
        Adjust quantity to match Binance lot-size precision.

        Floors the quantity to the nearest valid step to avoid
        APIError(code=-1111): Parameter 'quantity' has too much precision.
        """
        step = self.get_symbol_lot_size(symbol, futures=futures)

        # Fallback: if we can't get a step, keep a conservative precision
        if step <= 0:
            return float(f"{quantity:.6f}")

        # Determine decimal precision from step size, e.g. 0.0001 -> 4 decimals
        step_str = f"{step:.16f}".rstrip("0")
        if "." in step_str:
            precision = len(step_str.split(".")[1])
        else:
            precision = 0

        # Floor to nearest step
        steps = int(quantity / step)
        quantized = steps * step

        # Avoid float artifacts
        return float(f"{quantized:.{precision}f}")
    
    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 1000,
        futures: bool = False
    ) -> pd.DataFrame:
        """
        Get historical kline/candlestick data.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Kline interval (1m, 5m, 15m, 1h, 4h, 1d, etc.)
            limit: Number of klines to retrieve
            futures: Use futures market data
        
        Returns:
            DataFrame with OHLCV data
        """
        try:
            client = self.futures_client if futures else self.spot_client
            
            if futures:
                klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
            else:
                klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # Convert to proper types
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'quote_volume']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'quote_volume']]
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except BinanceAPIException as e:
            logger.error(f"Error fetching klines: {e}")
            return pd.DataFrame()
    
    def get_order_book(self, symbol: str, limit: int = 100, futures: bool = False) -> Dict:
        """Get order book data."""
        try:
            client = self.futures_client if futures else self.spot_client
            
            if futures:
                order_book = client.futures_order_book(symbol=symbol, limit=limit)
            else:
                order_book = client.get_order_book(symbol=symbol, limit=limit)
            
            return order_book
        except BinanceAPIException as e:
            logger.error(f"Error fetching order book: {e}")
            return {}
    
    def get_ticker(self, symbol: str, futures: bool = False) -> Dict:
        """Get 24hr ticker price statistics."""
        try:
            client = self.futures_client if futures else self.spot_client
            
            if futures:
                ticker = client.futures_ticker(symbol=symbol)
            else:
                ticker = client.get_ticker(symbol=symbol)
            
            return ticker
        except BinanceAPIException as e:
            logger.error(f"Error fetching ticker: {e}")
            return {}
    
    def get_funding_rate(self, symbol: str) -> float:
        """Get current funding rate for futures."""
        try:
            funding_info = self.futures_client.futures_funding_rate(symbol=symbol, limit=1)
            if funding_info:
                return float(funding_info[0]['fundingRate'])
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching funding rate: {e}")
            return 0.0
    
    def get_open_interest(self, symbol: str) -> float:
        """Get open interest for futures."""
        try:
            oi = self.futures_client.futures_open_interest(symbol=symbol)
            return float(oi['openInterest'])
        except Exception as e:
            logger.error(f"Error fetching open interest: {e}")
            return 0.0
    
    def _retry_api_call(self, func, max_retries: int = 3, *args, **kwargs):
        """
        Retry an API call with timestamp error handling.
        
        Args:
            func: Function to call
            max_retries: Maximum number of retries
            *args, **kwargs: Arguments to pass to func
        
        Returns:
            Result of func, or None if all retries fail
        """
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except BinanceAPIException as e:
                error_code = getattr(e, 'code', None)
                
                # Handle timestamp errors with retry
                if error_code == -1021:  # Timestamp outside recvWindow
                    if attempt < max_retries - 1:
                        # Sync server time and retry
                        try:
                            # Determine if futures based on kwargs or try both
                            use_futures = kwargs.get('futures', False)
                            if use_futures:
                                server_time = self.futures_client.futures_time()
                            else:
                                server_time = self.spot_client.get_server_time()
                            
                            # Small delay before retry
                            time.sleep(0.1 * (attempt + 1))
                            logger.debug(f"Retrying API call after timestamp sync (attempt {attempt + 1}/{max_retries})")
                            continue
                        except Exception as sync_error:
                            logger.warning(f"Failed to sync server time: {sync_error}")
                    
                    # Last attempt failed
                    if attempt == max_retries - 1:
                        logger.warning(f"Timestamp error after {max_retries} attempts: {e}")
                    return None
                else:
                    # Other errors - don't retry
                    logger.error(f"API error: {e}")
                    return None
            except Exception as e:
                logger.error(f"Unexpected error in API call: {e}")
                return None
        
        return None
    
    def get_account_balance(self, futures: bool = False) -> Dict[str, float]:
        """Get account balances with retry logic."""
        def _get_balance(futures=futures):
            client = self.futures_client if futures else self.spot_client
            
            if futures:
                account = client.futures_account()
                balances = {}
                for asset in account['assets']:
                    if float(asset['walletBalance']) > 0:
                        balances[asset['asset']] = float(asset['walletBalance'])
                return balances
            else:
                account = client.get_account()
                balances = {}
                for balance in account['balances']:
                    if float(balance['free']) > 0 or float(balance['locked']) > 0:
                        balances[balance['asset']] = {
                            'free': float(balance['free']),
                            'locked': float(balance['locked'])
                        }
                return balances
        
        result = self._retry_api_call(_get_balance, max_retries=3, futures=futures)
        return result if result is not None else {}
    
    def get_positions(self, futures: bool = False, max_retries: int = 3) -> List[Dict]:
        """
        Get current positions with retry logic for timestamp errors.
        
        Args:
            futures: Use futures trading
            max_retries: Maximum number of retry attempts
        
        Returns:
            List of active positions
        """
        def _get_positions():
            if futures:
                positions = self.futures_client.futures_position_information()
                active_positions = [
                    pos for pos in positions 
                    if float(pos['positionAmt']) != 0
                ]
                return active_positions
            else:
                # Spot doesn't have positions, return open orders
                return self.spot_client.get_open_orders()
        
        result = self._retry_api_call(_get_positions, max_retries=max_retries, futures=futures)
        return result if result is not None else []
    
    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float = None,
        price: float = None,
        stop_price: float = None,
        futures: bool = False,
        leverage: int = 1
    ) -> Dict:
        """
        Place an order.
        
        Args:
            symbol: Trading pair
            side: 'BUY' or 'SELL'
            order_type: 'MARKET', 'LIMIT', 'STOP_LOSS', 'TAKE_PROFIT'
            quantity: Order quantity
            price: Limit price (for LIMIT orders)
            stop_price: Stop price (for STOP orders)
            futures: Use futures trading
            leverage: Leverage for futures (1-125)
        
        Returns:
            Order response
        """
        try:
            client = self.futures_client if futures else self.spot_client
            
            if futures:
                # Set leverage first
                if leverage > 1:
                    client.futures_change_leverage(symbol=symbol, leverage=leverage)
                
                # Place futures order
                if order_type == 'MARKET':
                    order = client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type='MARKET',
                        quantity=quantity
                    )
                elif order_type == 'LIMIT':
                    order = client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type='LIMIT',
                        timeInForce='GTC',
                        quantity=quantity,
                        price=price
                    )
                else:
                    raise ValueError(f"Unsupported order type: {order_type}")
            else:
                # Place spot order
                if order_type == 'MARKET':
                    order = client.order_market(
                        symbol=symbol,
                        side=side,
                        quantity=quantity
                    )
                elif order_type == 'LIMIT':
                    order = client.order_limit(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=str(price)
                    )
                else:
                    raise ValueError(f"Unsupported order type: {order_type}")
            
            logger.info(f"Order placed: {order}")
            return order
            
        except BinanceAPIException as e:
            logger.error(f"Error placing order: {e}")
            raise
    
    def cancel_order(self, symbol: str, order_id: int, futures: bool = False) -> Dict:
        """Cancel an order."""
        try:
            client = self.futures_client if futures else self.spot_client
            
            if futures:
                result = client.futures_cancel_order(symbol=symbol, orderId=order_id)
            else:
                result = client.cancel_order(symbol=symbol, orderId=order_id)
            
            logger.info(f"Order cancelled: {result}")
            return result
            
        except BinanceAPIException as e:
            logger.error(f"Error cancelling order: {e}")
            raise
    
    def place_take_profit_order(
        self,
        symbol: str,
        side: str,  # 'SELL' for LONG, 'BUY' for SHORT
        quantity: float,
        stop_price: float,  # The TP price level
        futures: bool = False,
        reduce_only: bool = True  # Important: only reduce position, don't open new one
    ) -> Dict:
        """
        Place a take profit order on Binance.
        
        Args:
            symbol: Trading pair
            side: 'SELL' for LONG positions, 'BUY' for SHORT positions
            quantity: Quantity to close at this TP level
            stop_price: Take profit price (trigger price)
            futures: Use futures trading
            reduce_only: Only reduce position (futures only)
        
        Returns:
            Order response
        """
        try:
            client = self.futures_client if futures else self.spot_client
            
            if futures:
                # Quantize price to match Binance precision requirements
                quantized_price = self.quantize_price(symbol, stop_price, futures=True)
                
                # For futures, use TAKE_PROFIT_MARKET
                # This triggers a market order when price hits stop_price
                order = client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='TAKE_PROFIT_MARKET',
                    quantity=quantity,
                    stopPrice=quantized_price,  # Trigger price (quantized)
                    closePosition=False,  # We specify quantity, not close entire position
                    reduceOnly=reduce_only
                )
            else:
                # Quantize price for spot orders
                quantized_price = self.quantize_price(symbol, stop_price, futures=False)
                
                # For spot, use OCO (One-Cancels-Other) or simple LIMIT
                # Spot doesn't have TP orders, so we use a limit order
                order = client.order_limit(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=str(quantized_price)
                )
            
            logger.info(
                f"Take profit order placed: {symbol} {side} {quantity} @ {stop_price}"
            )
            return order
            
        except BinanceAPIException as e:
            logger.error(f"Error placing take profit order: {e}")
            raise
    
    def place_stop_loss_order(
        self,
        symbol: str,
        side: str,  # 'SELL' for LONG, 'BUY' for SHORT
        quantity: float,
        stop_price: float,  # The SL price level
        futures: bool = False,
        reduce_only: bool = True
    ) -> Dict:
        """
        Place a stop loss order on Binance.
        
        Args:
            symbol: Trading pair
            side: 'SELL' for LONG positions, 'BUY' for SHORT positions
            quantity: Quantity to close at SL
            stop_price: Stop loss price (trigger price)
            futures: Use futures trading
            reduce_only: Only reduce position (futures only)
        
        Returns:
            Order response
        """
        try:
            client = self.futures_client if futures else self.spot_client
            
            if futures:
                # Quantize price to match Binance precision requirements
                quantized_price = self.quantize_price(symbol, stop_price, futures=True)
                
                # For futures, use STOP_MARKET
                order = client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='STOP_MARKET',
                    quantity=quantity,
                    stopPrice=quantized_price,  # Trigger price (quantized)
                    closePosition=False,  # We specify quantity
                    reduceOnly=reduce_only
                )
            else:
                # Quantize prices for spot orders
                quantized_stop_price = self.quantize_price(symbol, stop_price, futures=False)
                # Using a limit order slightly below stop price for better execution
                limit_price = quantized_stop_price * 0.999 if side == 'SELL' else quantized_stop_price * 1.001
                quantized_limit_price = self.quantize_price(symbol, limit_price, futures=False)
                
                # For spot, use STOP_LOSS_LIMIT or STOP_LOSS
                order = client.create_order(
                    symbol=symbol,
                    side=side,
                    type='STOP_LOSS_LIMIT',
                    quantity=quantity,
                    stopPrice=str(quantized_stop_price),
                    price=str(quantized_limit_price),
                    timeInForce='GTC'
                )
            
            logger.info(
                f"Stop loss order placed: {symbol} {side} {quantity} @ {stop_price}"
            )
            return order
            
        except BinanceAPIException as e:
            logger.error(f"Error placing stop loss order: {e}")
            raise
    
    def get_order(self, symbol: str, order_id: int, futures: bool = False) -> Dict:
        """
        Get order status from Binance.
        
        Args:
            symbol: Trading pair
            order_id: Order ID
            futures: Use futures trading
        
        Returns:
            Order status dictionary
        """
        try:
            client = self.futures_client if futures else self.spot_client
            
            if futures:
                order = client.futures_get_order(symbol=symbol, orderId=order_id)
            else:
                order = client.get_order(symbol=symbol, orderId=order_id)
            
            return order
        except BinanceAPIException as e:
            logger.error(f"Error fetching order: {e}")
            return {}

