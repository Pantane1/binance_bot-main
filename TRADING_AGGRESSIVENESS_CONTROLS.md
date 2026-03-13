# Trading Aggressiveness Controls

This document explains all the parameters that control how "reckless" or "conservative" your trading bot is.

## 🎯 Primary Controls

### 1. **Confidence Threshold** (Main Prediction Filter)

**Location**: `config/config.yaml` → `prediction.confidence_threshold`

```yaml
prediction:
  confidence_threshold: 0.65  # Minimum confidence to execute trade
```

**What it does**: 
- Filters out predictions where models don't agree enough
- Higher = More conservative (fewer trades, higher quality)
- Lower = More aggressive (more trades, lower quality)

**Values**:
- `0.90+` = Very conservative (only highest confidence trades)
- `0.65-0.75` = Balanced (default)
- `0.50-0.65` = More aggressive (takes more trades)
- `0.30-0.50` = Very aggressive (takes most signals)
- `<0.30` = Extremely reckless (takes almost everything)

**Recommendation**: Start at `0.50` for testing, increase to `0.65+` for production.

---

### 2. **Risk Per Trade**

**Location**: `config/config.yaml` → `trading.risk.risk_per_trade`

```yaml
trading:
  risk:
    risk_per_trade: 0.015  # risk 1.5% of equity per trade
```

**What it does**: 
- Controls how much of your account you risk on each trade
- Higher = More aggressive (bigger positions)
- Lower = More conservative (smaller positions)

**Values**:
- `0.005` (0.5%) = Very conservative
- `0.01` (1%) = Conservative
- `0.015` (1.5%) = Moderate (current)
- `0.02` (2%) = Aggressive
- `0.03+` (3%+) = Very aggressive

---

### 3. **Max Position Size**

**Location**: `config/config.yaml` → `trading.risk.max_position_size`

```yaml
trading:
  risk:
    max_position_size: 0.05  # 5% of portfolio per trade (notional)
```

**What it does**: 
- Maximum position size as percentage of portfolio
- Caps how much you can put into a single trade
- Higher = Can take larger positions

**Values**:
- `0.02` (2%) = Very conservative
- `0.05` (5%) = Moderate (current)
- `0.10` (10%) = Aggressive
- `0.20+` (20%+) = Very aggressive

---

### 4. **Max Positions Per Symbol**

**Location**: `config/config.yaml` → `trading.max_positions_per_symbol`

```yaml
trading:
  max_positions_per_symbol: 3  # Allow up to 3 concurrent positions per symbol/direction
```

**What it does**: 
- Controls how many positions you can have open at once per symbol
- Higher = More aggressive (can pyramid/add to positions)
- Lower = More conservative (one position at a time)

**Values**:
- `1` = Conservative (one position per symbol)
- `2-3` = Moderate (current: 3)
- `5+` = Aggressive (can build large positions)

---

### 5. **Risk/Reward Ratio**

**Location**: `config/config.yaml` → `trading.risk.risk_reward_ratio`

```yaml
trading:
  risk:
    risk_reward_ratio: 0.5  # 1:2 risk to reward (more generous, TP closer)
```

**What it does**: 
- Controls how far take profit is from stop loss
- Lower ratio = More aggressive (easier to hit TP, more frequent wins)
- Higher ratio = More conservative (harder to hit TP, but bigger wins)

**Values**:
- `0.33` (1:3) = Conservative (risk $1 to make $3)
- `0.5` (1:2) = Moderate (current: risk $1 to make $2)
- `0.67` (1:1.5) = Aggressive (risk $1 to make $1.50)
- `1.0` (1:1) = Very aggressive (risk $1 to make $1)

---

### 6. **Stop Loss & Take Profit**

**Location**: `config/config.yaml` → `trading.risk.stop_loss_pct` and `take_profit_pct`

```yaml
trading:
  risk:
    stop_loss_pct: 0.015    # 1.5% stop loss (tighter)
    take_profit_pct: 0.03   # 3% take profit (2x stop loss)
```

**What it does**: 
- Stop loss: How far price can move against you before exit
- Take profit: How far price needs to move in your favor to exit
- Tighter stops = More aggressive (more frequent exits, smaller losses)
- Wider stops = More conservative (fewer exits, bigger losses)

**Values**:
- **Stop Loss**: `0.01` (1%) = Tight, `0.02` (2%) = Moderate, `0.05` (5%) = Wide
- **Take Profit**: `0.02` (2%) = Close, `0.05` (5%) = Moderate, `0.10` (10%) = Far

---

### 7. **Max Leverage** (Futures Only)

**Location**: `config/config.yaml` → `trading.risk.max_leverage`

```yaml
trading:
  risk:
    max_leverage: 15  # up to 15x leverage on futures
```

**What it does**: 
- Maximum leverage for futures trading
- Higher = More aggressive (bigger positions, higher risk)
- Lower = More conservative (smaller positions, lower risk)

**Values**:
- `1x` = No leverage (spot-like)
- `3-5x` = Conservative
- `10-15x` = Moderate (current: 15x)
- `20-50x` = Aggressive
- `100x+` = Extremely aggressive (high liquidation risk)

---

### 8. **Max Daily Loss**

**Location**: `config/config.yaml` → `trading.risk.max_daily_loss`

```yaml
trading:
  risk:
    max_daily_loss: 0.05  # 5% max daily loss
```

**What it does**: 
- Stops trading if daily losses exceed this threshold
- Higher = More aggressive (allows bigger daily drawdowns)
- Lower = More conservative (stops trading sooner)

**Values**:
- `0.02` (2%) = Very conservative
- `0.05` (5%) = Moderate (current)
- `0.10` (10%) = Aggressive
- `0.20+` (20%+) = Very aggressive

---

## 🎛️ Quick Presets

### **Very Conservative** (Safe, Few Trades)
```yaml
prediction:
  confidence_threshold: 0.75

trading:
  risk:
    risk_per_trade: 0.01        # 1%
    max_position_size: 0.03     # 3%
    risk_reward_ratio: 0.33      # 1:3
    stop_loss_pct: 0.02         # 2%
    take_profit_pct: 0.06        # 6%
    max_leverage: 5              # 5x
    max_daily_loss: 0.03         # 3%
  max_positions_per_symbol: 1
```

### **Moderate** (Current Settings)
```yaml
prediction:
  confidence_threshold: 0.65

trading:
  risk:
    risk_per_trade: 0.015        # 1.5%
    max_position_size: 0.05      # 5%
    risk_reward_ratio: 0.5       # 1:2
    stop_loss_pct: 0.015         # 1.5%
    take_profit_pct: 0.03        # 3%
    max_leverage: 15             # 15x
    max_daily_loss: 0.05         # 5%
  max_positions_per_symbol: 3
```

### **Aggressive** (More Trades, Higher Risk)
```yaml
prediction:
  confidence_threshold: 0.50

trading:
  risk:
    risk_per_trade: 0.025        # 2.5%
    max_position_size: 0.10      # 10%
    risk_reward_ratio: 0.67      # 1:1.5
    stop_loss_pct: 0.01          # 1%
    take_profit_pct: 0.015       # 1.5%
    max_leverage: 25              # 25x
    max_daily_loss: 0.10          # 10%
  max_positions_per_symbol: 5
```

### **Very Aggressive** (Reckless, Many Trades)
```yaml
prediction:
  confidence_threshold: 0.35

trading:
  risk:
    risk_per_trade: 0.05         # 5%
    max_position_size: 0.20      # 20%
    risk_reward_ratio: 1.0       # 1:1
    stop_loss_pct: 0.005         # 0.5%
    take_profit_pct: 0.005       # 0.5%
    max_leverage: 50              # 50x
    max_daily_loss: 0.20          # 20%
  max_positions_per_symbol: 10
```

---

## 📊 Impact Summary

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| **confidence_threshold** | More trades (aggressive) | Fewer trades (conservative) |
| **risk_per_trade** | Smaller positions (conservative) | Bigger positions (aggressive) |
| **max_position_size** | Smaller positions (conservative) | Bigger positions (aggressive) |
| **max_positions_per_symbol** | Fewer positions (conservative) | More positions (aggressive) |
| **risk_reward_ratio** | Easier TP (aggressive) | Harder TP (conservative) |
| **stop_loss_pct** | Tighter stops (aggressive) | Wider stops (conservative) |
| **max_leverage** | Less leverage (conservative) | More leverage (aggressive) |
| **max_daily_loss** | Stops sooner (conservative) | Allows bigger losses (aggressive) |

---

## 🔧 How to Adjust

1. **Open** `config/config.yaml`
2. **Find** the parameter you want to change
3. **Modify** the value
4. **Save** the file
5. **Restart** the bot (`python main.py`)

**Note**: Changes take effect immediately on restart. No code changes needed!

---

## ⚠️ Warnings

- **Lower confidence threshold** = More trades but lower quality
- **Higher leverage** = Bigger gains but higher liquidation risk
- **Tighter stops** = More frequent exits (good and bad)
- **Higher risk per trade** = Faster account growth or faster account loss

**Start conservative and gradually increase aggressiveness as you gain confidence!**

