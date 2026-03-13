# Concurrent Trading & Dynamic Order Adjustment

## Overview

The trading bot now supports **concurrent processing** of multiple symbols and **dynamic order adjustment** based on market conditions. This allows the bot to:

1. **Process all symbols simultaneously** instead of sequentially
2. **Place orders immediately** when confident signals are generated
3. **Dynamically adjust stop-loss orders** on the exchange as trailing stops move
4. **Monitor and update orders** based on real-time market conditions

---

## 1. Concurrent Symbol Processing

### How It Works

Previously, the bot processed symbols **sequentially** (one at a time):

```python
for symbol in symbols:
    self.run_trading_cycle(symbol)  # Wait for each to complete
```

Now, it processes all symbols **concurrently** using `ThreadPoolExecutor`:

```python
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    future_to_symbol = {
        executor.submit(self.run_trading_cycle, symbol): symbol
        for symbol in symbols
    }
    
    for future in as_completed(future_to_symbol):
        symbol = future_to_symbol[future]
        try:
            future.result()  # Handle any exceptions
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
```

### Benefits

- **Faster execution**: All symbols processed in parallel
- **Better opportunity capture**: No delay between symbols
- **Independent processing**: One symbol's error doesn't block others
- **Configurable concurrency**: Control via `trading.max_concurrent_symbols` in `config.yaml`

### Configuration

```yaml
trading:
  max_concurrent_symbols: 10  # Maximum concurrent symbols (default: all)
```

---

## 2. Dynamic Stop-Loss Order Adjustment

### How It Works

When a trailing stop moves (due to favorable price movement), the bot:

1. **Detects the change** in `should_exit_position()` when trailing stop is recalculated
2. **Cancels the old SL order** on Binance
3. **Places a new SL order** at the updated price
4. **Updates position tracking** with the new order ID

### Implementation Details

The `update_stop_loss_order()` method in `TradeExecutor`:

```python
def update_stop_loss_order(self, position: Dict, new_stop_loss: float) -> bool:
    """
    Update stop loss order on exchange when trailing stop moves.
    
    - Cancels old SL order
    - Places new SL order at updated price
    - Updates position['sl_order_id']
    """
```

### When Orders Are Updated

Orders are updated when:
- **Trailing stop activates** (price reaches `activate_rr` threshold)
- **Trailing stop moves** (price continues favorably)
- **Change is significant** (≥ 0.1% of entry price to avoid excessive API calls)

### Example Flow

```
1. Position opened: LONG BTCUSDT @ $90,000 | SL: $88,500
2. Price moves to $91,000 (1R profit reached)
3. Trailing stop activates: SL moves to $90,090 (1% trail)
4. Bot cancels old SL order @ $88,500
5. Bot places new SL order @ $90,090
6. Price continues to $92,000
7. Trailing stop moves: SL moves to $91,080
8. Bot cancels old SL order @ $90,090
9. Bot places new SL order @ $91,080
```

---

## 3. Order Placement Strategy

### Immediate Order Placement

When a signal is generated with sufficient confidence:

1. **Entry order** (MARKET) → Executes immediately
2. **TP orders** (TAKE_PROFIT_MARKET) → Placed immediately, wait for triggers
3. **SL order** (STOP_MARKET) → Placed immediately, waits for trigger

All orders are **visible in Binance** and **active on the exchange**.

### Order Types

**For Futures:**
- `TAKE_PROFIT_MARKET`: Triggers market order when price hits TP level
- `STOP_MARKET`: Triggers market order when price hits SL level
- Both use `reduceOnly=True` to ensure they only close positions

**For Spot:**
- `LIMIT` orders for TP (executes at limit price)
- `STOP_LOSS_LIMIT` for SL (triggers limit order at stop price)

---

## 4. Market Condition Monitoring

### What Gets Monitored

The bot continuously monitors:

1. **Price movements** → Updates trailing stops
2. **TP order fills** → Checks exchange order status
3. **SL order status** → Verifies orders are still active
4. **Position PnL** → Tracks unrealized gains/losses

### Monitoring Frequency

- **Every trading cycle** (default: 60 seconds)
- **Per symbol** (concurrently for all symbols)
- **Real-time updates** when trailing stops move

### Dynamic Adjustments

The bot adjusts orders based on:

- **Trailing stop movement** → Updates SL orders
- **Partial TP fills** → Updates remaining position size
- **Market volatility** → Adjusts stop distances (via risk manager)
- **Liquidation risk** → Moves stops to protect capital

---

## 5. Benefits

### 1. Speed & Efficiency
- Process all symbols simultaneously
- No waiting between symbols
- Faster signal execution

### 2. Risk Management
- Dynamic SL adjustment protects profits
- Orders always reflect current risk levels
- Exchange-side execution (works even if bot is down)

### 3. Transparency
- All orders visible in Binance
- Real-time order updates
- Clear tracking of TP/SL levels

### 4. Reliability
- Exchange handles execution
- Orders persist even if bot restarts
- Automatic order updates

---

## 6. Configuration Example

```yaml
trading:
  mode: "futures"
  symbols:
    - "BTCUSDT"
    - "ETHUSDT"
    - "XRPUSDT"
    # ... more symbols
  
  max_concurrent_symbols: 10  # Process up to 10 symbols concurrently
  
  risk:
    trailing_stop:
      enabled: true
      activate_rr: 0.5  # Activate after 0.5R profit
      trail_pct: 0.005  # Trail 0.5% behind peak
```

---

## 7. Logging & Monitoring

### Example Log Output

```
2025-12-17 14:30:00 - __main__ - INFO - Running trading cycle for BTCUSDT
2025-12-17 14:30:00 - __main__ - INFO - Running trading cycle for ETHUSDT
2025-12-17 14:30:00 - __main__ - INFO - Running trading cycle for XRPUSDT
...
2025-12-17 14:30:15 - trading.strategy - INFO - Trailing stop updated on exchange for BTCUSDT: 88500.00 -> 90090.00 (Order ID: 12345678)
2025-12-17 14:30:20 - trading.executor - INFO - Updated SL order for ETHUSDT: 2450.00 -> 2472.25 (Order ID: 12345679)
```

---

## 8. Best Practices

1. **Monitor API rate limits**: Concurrent processing may hit rate limits faster
2. **Adjust concurrency**: Set `max_concurrent_symbols` based on your API tier
3. **Watch order updates**: Trailing stops update frequently in volatile markets
4. **Check Binance dashboard**: Verify orders are being placed/updated correctly
5. **Monitor logs**: Watch for order update failures

---

## 9. Troubleshooting

### Orders Not Updating

- Check API permissions (need futures trading enabled)
- Verify order IDs are stored correctly
- Check logs for cancellation/placement errors
- Ensure trailing stop is enabled in config

### Concurrent Processing Issues

- Reduce `max_concurrent_symbols` if hitting rate limits
- Check for thread safety issues in logs
- Verify all symbols are valid on exchange

### Order Placement Failures

- Check price precision (should be handled automatically)
- Verify account has sufficient margin
- Check for IP restrictions on API key
- Ensure testnet/mainnet matches your API keys

---

## Summary

The bot now:
- ✅ Processes all symbols concurrently
- ✅ Places orders immediately when confident
- ✅ Dynamically adjusts SL orders as trailing stops move
- ✅ Monitors market conditions continuously
- ✅ Updates orders on exchange in real-time

This creates a more responsive, efficient, and risk-aware trading system that adapts to market conditions automatically.

