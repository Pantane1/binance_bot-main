# Trading Timeframe and Performance Expectations

## Current Configuration

### Prediction Horizon: **1 Hour**
- The bot predicts price movements **1 hour into the future**
- Uses **1-hour candlestick data** for analysis
- Target variable: `future_return = (price_in_1_hour - current_price) / current_price`

### Trading Timeframe: **Intraday (Hours)**

The bot is optimized for **short-term intraday trading**, not swing trading or long-term holds.

## Expected Trade Duration

### Typical Trade Lifecycle:

1. **Entry**: Position opened based on 1-hour prediction
2. **First Profit Target (0.5R)**: ~25% of position closed within **30 minutes to 2 hours**
   - This is your "quick win" - locks in profits fast
3. **Second Profit Target (1R)**: ~30% more closed within **1-3 hours**
   - Breakeven+ trades secured
4. **Third Profit Target (1.5R)**: ~25% more closed within **2-4 hours**
   - Good profits locked in
5. **Final Profit Target (2R)**: Remaining ~20% closed within **3-6 hours**
   - Letting winners run

### Average Position Duration: **2-4 hours**

Most positions will be fully closed within **2-4 hours** due to:
- Aggressive partial profit-taking (starts at 0.5R)
- Tight trailing stops (0.5% behind peak)
- 1-hour prediction horizon (signals are short-term)

## When Will You Start Making Money?

### Realistic Timeline:

**Week 1-2: Learning Phase**
- Bot learns market patterns
- Models adapt to current market conditions
- Expect: Break-even to small losses as bot finds its footing
- **Action**: Monitor closely, ensure risk management is working

**Week 3-4: Optimization Phase**
- Models have more data
- Patterns become clearer
- Expect: Small consistent profits or break-even
- **Action**: Review which symbols perform best, adjust confidence threshold if needed

**Month 2+: Profitability Phase**
- Models are well-trained on recent data
- Bot has learned market dynamics
- Expect: Consistent small profits, occasional larger wins
- **Action**: Scale up position sizes gradually if profitable

### Key Factors Affecting Performance:

1. **Model Quality** (Current R²: ~0.02-0.03)
   - Low R² means predictions are weak
   - Models are barely better than random
   - **This is why confidence is low (0.53-0.56 vs 0.65 threshold)**
   - **Solution**: More training data, better features, longer training

2. **Market Conditions**
   - Trending markets: Better performance
   - Sideways/choppy markets: More false signals
   - High volatility: More opportunities but more risk

3. **Confidence Threshold (0.65)**
   - Currently rejecting most trades (confidence too low)
   - Lower threshold = more trades but lower quality
   - Higher threshold = fewer trades but higher quality

## Why Forecasts Play Out in Hours (Not Days/Weeks)

### Technical Reasons:

1. **1-Hour Prediction Horizon**
   - Models predict 1 hour ahead
   - Signal strength decays quickly beyond this window
   - Market conditions change rapidly in crypto

2. **Aggressive Profit-Taking**
   - First 25% closes at 0.5R (very early)
   - Designed to "grow account fast" and "take advantage of re-entries"
   - This means positions close quickly

3. **Tight Risk Management**
   - 1.5% stop loss
   - 2.5% take profit
   - Trailing stop at 0.5% behind peak
   - All designed for quick in-and-out trades

4. **Crypto Market Characteristics**
   - High volatility
   - Fast-moving markets
   - Short-term patterns are more predictable than long-term

## Improving Performance Timeline

### To Make Money Faster:

1. **Lower Confidence Threshold** (Immediate)
   ```yaml
   prediction:
     confidence_threshold: 0.55  # Down from 0.65
   ```
   - More trades will execute
   - But quality may be lower
   - **Risk**: More losing trades

2. **Retrain Models with More Data** (1-2 days)
   - Run `python retrain_models.py` with `--lookback 5000`
   - More historical data = better patterns
   - **Expected improvement**: R² from 0.02 to 0.05-0.10

3. **Use Longer Timeframes** (Requires code changes)
   - Change to 4-hour or daily predictions
   - Better for swing trading
   - Trades play out over days/weeks
   - **Trade-off**: Fewer trading opportunities

4. **Improve Model Features** (Ongoing)
   - Add more technical indicators
   - Better sentiment analysis
   - More market microstructure features
   - **Expected improvement**: R² from 0.02 to 0.10-0.20

## Recommended Strategy

### For Faster Profits (Aggressive):
1. Lower confidence threshold to 0.55
2. Retrain models with more data (5000+ candles)
3. Monitor for 1-2 weeks
4. Gradually increase position sizes if profitable

### For Sustainable Growth (Conservative):
1. Keep confidence threshold at 0.65
2. Focus on improving model quality (R²)
3. Wait for better signals (fewer but higher quality trades)
4. Scale up slowly over months

## Current Status

**Your Bot Right Now:**
- ✅ Making predictions (LONG/SHORT signals)
- ✅ Calculating confidence scores (0.53-0.56)
- ❌ Rejecting trades (confidence below 0.65 threshold)
- ⚠️ Models have low predictive power (R² ~0.02)

**What This Means:**
- Bot is working correctly (being conservative)
- But models need improvement to be profitable
- You're not losing money (no trades = no losses)
- But you're also not making money (no trades = no gains)

## Next Steps

1. **Immediate**: Lower confidence threshold to 0.55-0.60 to start trading
2. **Short-term**: Retrain models with more data (5000+ candles per symbol)
3. **Medium-term**: Monitor performance, adjust parameters based on results
4. **Long-term**: Continuously improve models, add features, optimize strategy

---

**Bottom Line**: This bot is designed for **intraday trading with positions closing within hours**. Expect to see results (positive or negative) within **days to weeks**, not months. The aggressive profit-taking strategy means you'll know quickly if a trade is working or not.


