# Margin Calculation Guide

## Overview

Margin is the amount of capital you need to lock up to open a position. The bot calculates margin based on **risk management rules** and **leverage settings**.

---

## Key Factors That Determine Margin

### 1. **Risk Per Trade** (`risk_per_trade`)
- **Current Setting**: 2% of account balance
- **Location**: `config.yaml` → `trading.risk.risk_per_trade: 0.02`
- **Impact**: Determines how much capital you're willing to risk if the stop loss is hit

### 2. **Stop Loss Distance** (`stop_loss_pct`)
- **Current Setting**: 2.5% from entry price
- **Location**: `config.yaml` → `trading.risk.stop_loss_pct: 0.025`
- **Impact**: Tighter stop loss = larger position size (to risk the same dollar amount)
- **Formula**: `price_risk = abs(entry_price - stop_loss)`

### 3. **Maximum Position Size** (`max_position_size`)
- **Current Setting**: 7% of account balance
- **Location**: `config.yaml` → `trading.risk.max_position_size: 0.07`
- **Impact**: Caps the maximum position size regardless of risk calculations

### 4. **Leverage** (`max_leverage`)
- **Current Setting**: 8x for futures
- **Location**: `config.yaml` → `trading.risk.max_leverage: 8`
- **Impact**: Reduces required margin for futures trading (margin = notional / leverage)

### 5. **Account Balance**
- **Impact**: All calculations are based on your current account balance
- **Note**: For futures, the calculation uses `balance × leverage` to determine notional position size

---

## Calculation Process

### Step 1: Calculate Risk Amount
```python
risk_amount = account_balance × risk_per_trade
# Example: $10,000 × 0.02 = $200 risk per trade
```

### Step 2: Calculate Price Risk
```python
price_risk = abs(entry_price - stop_loss)
# Example: Entry $50,000, SL $48,750 → $1,250 risk per BTC
```

### Step 3: Calculate Position Size (Base Currency)
```python
position_size = risk_amount / price_risk
# Example: $200 / $1,250 = 0.16 BTC

# Capped by maximum position size:
max_position = account_balance × max_position_size
position_size = min(position_size, max_position)
# Example: min(0.16 BTC, $10,000 × 0.07 / $50,000) = min(0.16, 0.014) = 0.014 BTC
```

### Step 4: Calculate Notional Value
```python
notional_value = position_size × entry_price
# Example: 0.014 BTC × $50,000 = $700 notional
```

### Step 5: Calculate Required Margin

#### For Spot Trading (No Leverage):
```python
required_margin = notional_value
# Example: $700 margin required (100% of position value)
```

#### For Futures Trading (With Leverage):
```python
required_margin = notional_value / leverage
# Example: $700 / 8 = $87.50 margin required (12.5% of position value)
```

---

## Real-World Example

### Scenario:
- **Account Balance**: $10,000 USDT
- **Symbol**: BTCUSDT
- **Entry Price**: $50,000
- **Stop Loss**: $48,750 (2.5% below entry)
- **Trading Mode**: Futures
- **Leverage**: 8x

### Calculation:

1. **Risk Amount**: $10,000 × 0.02 = **$200**

2. **Price Risk**: $50,000 - $48,750 = **$1,250 per BTC**

3. **Position Size**: $200 / $1,250 = **0.16 BTC**
   - Max position cap: $10,000 × 0.07 / $50,000 = **0.014 BTC**
   - **Final position size**: **0.014 BTC** (capped by max_position_size)

4. **Notional Value**: 0.014 BTC × $50,000 = **$700**

5. **Required Margin**: $700 / 8 = **$87.50**

### Result:
- **Position Size**: 0.014 BTC
- **Notional Value**: $700
- **Margin Required**: $87.50 (8.75% of account balance)
- **Risk if SL Hit**: $200 (2% of account balance)

---

## How to Adjust Margin Usage

### To Use More Margin:
1. **Increase `max_position_size`** (e.g., 0.07 → 0.10)
   - Allows larger positions
   - **Warning**: Increases risk per trade

2. **Increase `risk_per_trade`** (e.g., 0.02 → 0.03)
   - Risks more capital per trade
   - **Warning**: Higher drawdown potential

3. **Increase `max_leverage`** (e.g., 8x → 10x)
   - Reduces margin requirement for same position size
   - **Warning**: Higher liquidation risk

4. **Tighten `stop_loss_pct`** (e.g., 0.025 → 0.02)
   - Allows larger position size for same risk amount
   - **Warning**: More likely to be stopped out

### To Use Less Margin:
1. **Decrease `max_position_size`** (e.g., 0.07 → 0.05)
   - Limits maximum position size

2. **Decrease `risk_per_trade`** (e.g., 0.02 → 0.015)
   - Risks less capital per trade

3. **Decrease `max_leverage`** (e.g., 8x → 5x)
   - Requires more margin for same position size
   - **Benefit**: Lower liquidation risk

4. **Widen `stop_loss_pct`** (e.g., 0.025 → 0.03)
   - Reduces position size for same risk amount
   - **Benefit**: Less likely to be stopped out

---

## Important Notes

### 1. **Leverage Multiplier Effect**
- With 8x leverage, you control **8×** the position size with the same margin
- Example: $100 margin → $800 notional position

### 2. **Position Size Capping**
- The `max_position_size` (7%) is a **hard cap**
- Even if risk calculations suggest a larger position, it will be capped at 7% of balance

### 3. **Risk Consistency**
- The bot always risks exactly `risk_per_trade` (2%) if stop loss is hit
- Position size adjusts automatically based on stop loss distance

### 4. **Liquidation Buffer**
- For futures, the bot ensures a 10% buffer above liquidation price
- This may reduce effective leverage if the buffer requirement is stricter

### 5. **Multiple Positions**
- Each position uses its own margin calculation
- Total margin usage = sum of all open positions
- `max_positions_per_symbol` (4) limits concurrent positions per symbol

---

## Current Configuration Summary

| Parameter | Value | Impact on Margin |
|-----------|-------|------------------|
| `risk_per_trade` | 2% | Base risk amount |
| `max_position_size` | 7% | Maximum position cap |
| `stop_loss_pct` | 2.5% | Affects position size calculation |
| `max_leverage` | 8x | Reduces margin requirement (futures) |
| `confidence_threshold` | 80% | Filters trades (indirectly affects margin usage) |

---

## Formula Summary

```python
# Position Size (Base Currency)
risk_amount = account_balance × risk_per_trade
price_risk = abs(entry_price - stop_loss)
position_size = min(risk_amount / price_risk, account_balance × max_position_size / entry_price)

# Notional Value
notional_value = position_size × entry_price

# Required Margin
if spot:
    margin = notional_value  # 100% margin
else:  # futures
    margin = notional_value / leverage  # Fractional margin
```

---

## Monitoring Margin Usage

The bot logs position details including:
- Position size (base currency)
- Leverage used
- Entry price
- Stop loss
- Take profit

Check logs for entries like:
```
Position opened: BTCUSDT LONG | Size: 0.014 | Leverage: 8x | Entry: $50,000
```

This tells you:
- **Size**: 0.014 BTC
- **Notional**: 0.014 × $50,000 = $700
- **Margin**: $700 / 8 = $87.50




