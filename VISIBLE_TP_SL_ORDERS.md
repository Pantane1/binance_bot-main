# Visible Take Profit & Stop Loss Orders

## Overview

The trading bot now places **visible TP and SL orders directly on Binance** when opening positions. This means you can see exactly where profit-taking and stop-loss orders are set in your Binance account, providing full transparency and peace of mind.

## What Changed

### Before
- Bot placed market orders to open positions
- Bot monitored positions and closed them when TP/SL levels were hit
- No visible orders in Binance until execution
- Relied on bot monitoring (could miss if bot is down)

### After
- Bot places market order to open position
- **Immediately places multiple TP orders** on Binance (visible in your account)
- **Immediately places SL order** on Binance (visible in your account)
- Exchange handles execution automatically
- Orders are visible and trackable in Binance

## How It Works

### When a Position Opens

1. **Entry Order**: Market order to open position
2. **TP Orders**: Multiple take-profit orders placed immediately:
   - 25% @ 0.5R (very early profit)
   - 30% @ 1.0R (first major exit)
   - 25% @ 1.5R (extended profit)
   - 20% @ 2.0R (final exit)
3. **SL Order**: Stop-loss order for full position size

### Order Types Used

**For Futures:**
- `TAKE_PROFIT_MARKET`: Triggers market order when price hits TP level
- `STOP_MARKET`: Triggers market order when price hits SL level
- Both use `reduceOnly=True` to ensure they only close positions

**For Spot:**
- `LIMIT` orders for TP (executes at limit price)
- `STOP_LOSS_LIMIT` for SL (triggers limit order at stop price)

## What You'll See in Binance

When a position opens, you'll see in your Binance account:

### Open Orders Tab
- **4 Take Profit orders** (one for each TP level)
  - Shows quantity (volume) for each
  - Shows trigger price for each
  - Shows order ID for tracking
- **1 Stop Loss order**
  - Shows full position size
  - Shows trigger price
  - Shows order ID

### Example Log Output

```
TP order placed: 25% (0.2500) @ 90675.00 (0.5R) - Order ID: 12345678
TP order placed: 30% (0.3000) @ 91350.00 (1.0R) - Order ID: 12345679
TP order placed: 25% (0.2500) @ 92025.00 (1.5R) - Order ID: 12345680
TP order placed: 20% (0.2000) @ 92700.00 (2.0R) - Order ID: 12345681
Stop loss order placed: 1.0000 @ 88650.00 - Order ID: 12345682
Position opened with 4 TP orders + 1 SL order: BTCUSDT LONG | Size: 1.0 | TP orders: ['25% @ 90675.00', '30% @ 91350.00', '25% @ 92025.00', '20% @ 92700.00'] | SL: 88650.00
```

## Benefits

### 1. **Full Transparency**
- See exactly where profits will be taken
- See exactly where stop loss is set
- Know the volume for each TP level

### 2. **Reliability**
- Exchange handles execution (not dependent on bot)
- Orders execute even if bot is down
- No missed profit-taking opportunities

### 3. **Peace of Mind**
- No anxiety about whether bot is monitoring correctly
- Can verify orders in Binance UI
- Full audit trail in Binance order history

### 4. **Better Execution**
- Exchange-level order execution (faster)
- No network delays between bot and exchange
- Automatic execution when price hits levels

## Order Tracking

The bot tracks TP orders and updates position state when they're filled:

- Monitors order status on exchange
- Updates `remaining_size` when TP orders fill
- Logs when each TP level is hit
- Tracks which TP levels have been executed

## Manual Close Behavior

If you manually close a position (or bot needs to close for other reasons):

- **Cancels remaining TP orders** (if not already filled)
- **Cancels SL order** (if not already triggered)
- Places market order to close remaining position

This prevents duplicate orders and ensures clean position management.

## Configuration

The TP/SL orders use the same configuration as before:

```yaml
trading:
  risk:
    stop_loss_pct: 0.015         # 1.5% stop loss
    take_profit_pct: 0.025       # 2.5% take profit
    
    partial_take_profits:
      - { fraction: 0.25, rr_multiple: 0.5 }  # 25% at 0.5R
      - { fraction: 0.30, rr_multiple: 1.0 }  # 30% at 1R
      - { fraction: 0.25, rr_multiple: 1.5 }  # 25% at 1.5R
      - { fraction: 0.20, rr_multiple: 2.0 }  # 20% at 2R
```

## Technical Details

### Order Precision
- All quantities are quantized to Binance's lot-size precision rules
- Prices are set to exact TP/SL levels from risk manager
- Uses `quantize_quantity()` to ensure valid order sizes

### Error Handling
- If TP order placement fails, logs error but continues
- If SL order placement fails, logs error but continues
- Position is still opened even if some orders fail (can be placed manually)

### Position State
- `tp_orders`: List of TP order info (order_id, price, quantity, fraction, rr_multiple)
- `sl_order_id`: Stop loss order ID
- `remaining_size`: Updated when TP orders fill

## Viewing Orders in Binance

### Futures Trading
1. Go to **Futures** → **Open Orders**
2. See all TP and SL orders listed
3. Orders show:
   - Symbol
   - Side (SELL for LONG, BUY for SHORT)
   - Quantity
   - Trigger Price
   - Order Type (TAKE_PROFIT_MARKET, STOP_MARKET)

### Spot Trading
1. Go to **Orders** → **Open Orders**
2. See TP limit orders and SL stop orders
3. Orders show:
   - Symbol
   - Side
   - Quantity
   - Price
   - Order Type

## Troubleshooting

### Orders Not Appearing
- Check API permissions (need Futures Trading enabled)
- Verify testnet vs mainnet keys match
- Check if position was actually opened
- Review logs for order placement errors

### Orders Filling Unexpectedly
- Check if price actually hit trigger levels
- Verify TP/SL prices are correct
- Review order history in Binance

### Partial TP Orders Not Filling
- Ensure quantities are above minimum lot size
- Check if price reached trigger levels
- Verify order status in Binance (might be rejected)

## Summary

The bot now provides **full transparency** by placing all TP and SL orders directly on Binance. You can:

- ✅ See exactly where profits will be taken
- ✅ See exactly where stop loss is set
- ✅ Know the volume for each TP level
- ✅ Trust exchange-level execution
- ✅ Have peace of mind with visible orders

All orders are visible in your Binance account immediately after position opens, giving you complete control and visibility over your trading strategy.

