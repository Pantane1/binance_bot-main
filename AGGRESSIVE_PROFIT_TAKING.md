# Aggressive Profit Taking Strategy

## Overview

The trading bot now uses an **aggressive profit-taking strategy** designed to:
1. **Grow the account fast** by locking in profits early and frequently
2. **Enable better re-entries** by scaling out positions while leaving room for additional entries

## Profit Taking Levels

The bot now scales out positions at **4 different profit levels**:

| Level | R Multiple | Fraction | Purpose |
|-------|-------------|----------|---------|
| 1 | 0.5R | 25% | **Very early profit** - locks in gains quickly |
| 2 | 1.0R | 30% | **First major exit** - secures initial target |
| 3 | 1.5R | 25% | **Extended profit** - captures more upside |
| 4 | 2.0R | 20% | **Let winners run** - final exit for remaining position |

**Total: 100% scaled out** across 4 levels, but positions can be re-entered after scaling.

## How It Works

### 1. Early Profit Locking (0.5R)
- Takes **25% of position** at just **0.5R profit**
- Example: If you risk $100 (1R), you take profit on 25% of position when you're up $50
- **Fast account growth** - profits are locked in very early

### 2. First Major Exit (1.0R)
- Takes **30% of position** at **1R profit** (risk-reward break-even)
- This is your "safety net" - you've now locked in enough profit to cover the risk
- **Disciplined gains** - ensures you don't give back profits

### 3. Extended Profit (1.5R)
- Takes **25% of position** at **1.5R profit**
- Captures additional upside while still leaving room for more
- **Compound growth** - multiple profit-taking events compound returns

### 4. Final Exit (2.0R)
- Takes remaining **20% of position** at **2.0R profit**
- Lets winners run while protecting most of the gains
- **Maximum profit** - captures the full move if it continues

## Re-Entry Strategy

After scaling out positions, the bot can **re-enter** if:
- The signal remains strong (high confidence)
- Existing positions are mostly scaled out (<30% remaining)
- Max positions per symbol not exceeded (5 positions allowed)

This allows you to:
- **Add to winners** - enter more size as the trend continues
- **Better entries** - re-enter at more favorable prices after taking profits
- **Compound positions** - build larger positions over time on strong trends

## Trailing Stop Protection

- **Activates at 0.5R** (very early)
- **Trails by 0.5%** behind peak price
- **Locks in profits** automatically as price moves in your favor
- **Protects against reversals** while allowing upside

## Example Trade Flow

### Scenario: LONG BTCUSDT at $90,000 with 1.5% stop loss ($88,650)

1. **Entry**: $90,000
2. **Stop Loss**: $88,650 (1.5% = $1,350 = 1R)
3. **Position Size**: 1 BTC

**Profit Taking Sequence:**

| Price | R Multiple | Action | Size Closed | Remaining | Profit Locked |
|-------|-------------|--------|-------------|-----------|---------------|
| $90,675 | 0.5R | Take 25% | 0.25 BTC | 0.75 BTC | +$168.75 |
| $91,350 | 1.0R | Take 30% | 0.30 BTC | 0.45 BTC | +$405.00 |
| $92,025 | 1.5R | Take 25% | 0.25 BTC | 0.20 BTC | +$506.25 |
| $92,700 | 2.0R | Take 20% | 0.20 BTC | 0.00 BTC | +$540.00 |

**Total Profit**: $1,620 (1.8% on full position, but locked in progressively)

**Re-Entry Opportunity:**
- After scaling to 0.45 BTC remaining, if price pulls back to $90,500 and signal is still strong
- Bot can enter a new position, effectively "averaging down" or "adding to winners"
- This compounds the position size while maintaining risk management

## Configuration

In `config/config.yaml`:

```yaml
trading:
  max_positions_per_symbol: 5  # Increased for aggressive scaling
  allow_reentry_after_scaling: true  # Enable re-entry after scaling out

  risk:
    take_profit_pct: 0.025  # 2.5% (more achievable, faster exits)
    
    partial_take_profits:
      - { fraction: 0.25, rr_multiple: 0.5 }  # 25% at 0.5R
      - { fraction: 0.30, rr_multiple: 1.0 }  # 30% at 1R
      - { fraction: 0.25, rr_multiple: 1.5 }  # 25% at 1.5R
      - { fraction: 0.20, rr_multiple: 2.0 }  # 20% at 2R
    
    trailing_stop:
      enabled: true
      activate_rr: 0.5      # Start trailing at 0.5R (very early)
      trail_pct: 0.005       # Tight trailing (0.5% behind peak)
```

## Benefits

1. **Fast Account Growth**
   - Profits locked in early (0.5R)
   - Multiple profit-taking events compound returns
   - Reduces risk of giving back gains

2. **Better Re-Entries**
   - Can add to positions after scaling out
   - Re-enter at better prices on pullbacks
   - Compound position size on strong trends

3. **Disciplined Gains**
   - Systematic profit-taking prevents greed
   - Trailing stops protect against reversals
   - Risk-reward maintained throughout

4. **Flexibility**
   - Positions can be scaled out and re-entered
   - Multiple positions per symbol allowed
   - Adapts to market conditions

## Risk Considerations

- **More frequent exits** mean smaller individual profits but more consistent gains
- **Re-entry** can increase position size if not managed carefully
- **Trailing stops** may exit early in volatile markets
- **Partial exits** reduce position size, so full trend capture is limited

## Tuning Aggressiveness

To make profit taking **even more aggressive**:
- Lower R multiples (e.g., 0.3R, 0.6R, 1.0R, 1.5R)
- Take larger fractions earlier (e.g., 40% at 0.5R)
- Reduce `take_profit_pct` to make targets easier to hit

To make profit taking **less aggressive**:
- Higher R multiples (e.g., 1.0R, 1.5R, 2.0R, 3.0R)
- Take smaller fractions (e.g., 20% at each level)
- Increase `take_profit_pct` for larger targets

## Summary

This aggressive profit-taking strategy is designed to:
- ✅ Lock in profits early and frequently
- ✅ Grow the account faster through compound gains
- ✅ Enable re-entries for better position building
- ✅ Maintain discipline while maximizing opportunities

The bot will now take profits at 4 different levels, starting as early as 0.5R, while still allowing re-entry opportunities to compound gains on strong trends.

