# Model Training & Strengthening Guide

This guide explains how to strengthen and retrain your trading models for better performance.

## Quick Start

### Basic Retraining

Retrain models with improved parameters:

```bash
python retrain_models.py
```

This will:
- Collect 2000 candles of historical data (default)
- Train all models with enhanced parameters
- Save models to `models/` directory
- Show performance metrics (R², RMSE, MAE)

### Retrain Single Symbol

Train models for a specific symbol:

```bash
python retrain_models.py --symbol BTCUSDT
```

### Per-Symbol Training

Train separate models for each symbol (better accuracy):

```bash
python retrain_models.py --per-symbol
```

### Custom Lookback Period

Use more historical data:

```bash
python retrain_models.py --lookback 3000
```

## What's Improved

### Enhanced Model Parameters

The retraining script uses stronger default parameters:

**XGBoost:**
- `n_estimators`: 500 (was 200)
- `max_depth`: 8 (was 6)
- `learning_rate`: 0.05 (was 0.1) - better generalization
- Added regularization: `min_child_weight`, `gamma`

**LightGBM:**
- `n_estimators`: 500 (was 200)
- `max_depth`: 8 (was 6)
- `learning_rate`: 0.05 (was 0.1)
- Added regularization: `min_child_samples`

**CatBoost:**
- `iterations`: 500 (was 200)
- `depth`: 8 (was 6)
- `learning_rate`: 0.05 (was 0.1)

**Random Forest:**
- `n_estimators`: 300 (was 200)
- `max_depth`: 12 (was 10)
- Added regularization: `min_samples_split`, `min_samples_leaf`

**Gradient Boosting:**
- `n_estimators`: 500 (was 200)
- `max_depth`: 8 (was 6)
- `learning_rate`: 0.05 (was 0.1)
- Added regularization

### More Training Data

- Default lookback increased to 2000 candles (was 1000)
- Can be customized with `--lookback` parameter
- More data = better model generalization

## Expected Improvements

With these enhancements, you should see:

- **R² Score**: +5-15% improvement
- **RMSE**: 10-20% reduction
- **Prediction Accuracy**: Better direction prediction
- **Confidence Scores**: More reliable confidence estimates

## Training Strategies

### 1. Combined Training (Default)

Trains one set of models on data from all symbols:

```bash
python retrain_models.py
```

**Pros:**
- More training data
- Faster training
- Generalizes across symbols

**Cons:**
- May not capture symbol-specific patterns

### 2. Per-Symbol Training

Trains separate models for each symbol:

```bash
python retrain_models.py --per-symbol
```

**Pros:**
- Captures symbol-specific patterns
- Better accuracy per symbol
- Models saved as `{SYMBOL}_{MODEL}.pkl`

**Cons:**
- Longer training time
- More model files to manage

### 3. Single Symbol Focus

Train models for your most important symbol:

```bash
python retrain_models.py --symbol BTCUSDT --lookback 3000
```

**Best for:**
- Focusing on major pairs
- Testing improvements
- Quick iteration

## When to Retrain

### Regular Retraining

**Recommended frequency:**
- **Daily**: For active trading
- **Weekly**: For moderate trading
- **Monthly**: For conservative trading

### Retrain When:

1. **Performance Degrades**: Model accuracy drops
2. **Market Regime Changes**: Bull to bear market, volatility shifts
3. **New Features Added**: After adding new indicators or data sources
4. **After Major Events**: Market crashes, regulatory changes
5. **Scheduled Maintenance**: Weekly/monthly routine

## Monitoring Model Performance

### Check Model Metrics

After retraining, check the logs:

```
XGBoost - Test RMSE: 0.003825, R²: 0.3714
LightGBM - Test RMSE: 0.003825, R²: 0.3714
CatBoost - Test RMSE: 0.003977, R²: 0.3204
```

**Good Metrics:**
- R² > 0.3 (for crypto, this is decent)
- RMSE < 0.01 (1% error)
- Train/test R² close (no overfitting)

### Compare Before/After

Before retraining, note current metrics. After retraining, compare:

- **R² improvement**: Higher is better
- **RMSE reduction**: Lower is better
- **Confidence scores**: More consistent predictions

## Advanced: Hyperparameter Tuning

The config has hyperparameter tuning enabled:

```yaml
models:
  hyperparameter_tuning:
    enabled: true
    method: "optuna"
    n_trials: 100
```

**Note**: This is configured but not yet fully implemented in the retraining script. For now, the enhanced default parameters provide good performance.

## Troubleshooting

### "No data collected"

- Check internet connection
- Verify Binance API is accessible
- Check symbol names are correct

### "Out of memory"

- Reduce `--lookback` (e.g., 1500 instead of 2000)
- Train fewer symbols at once
- Use `--symbol` to train one at a time

### "Models not improving"

- Increase `--lookback` to 3000+
- Try `--per-symbol` for symbol-specific models
- Check feature engineering is working
- Verify data quality

## Best Practices

1. **Start Conservative**: Retrain with default settings first
2. **Monitor Results**: Check metrics after each retraining
3. **Backup Models**: Keep old models before retraining
4. **Test Before Deploy**: Test new models on testnet first
5. **Regular Schedule**: Set up automated retraining (cron/scheduler)

## Automated Retraining

To set up automatic retraining, you can:

1. **Use cron (Linux/Mac)**:
   ```bash
   # Retrain daily at 2 AM
   0 2 * * * cd /path/to/tricast && python retrain_models.py
   ```

2. **Use Task Scheduler (Windows)**:
   - Create scheduled task
   - Run `python retrain_models.py` daily

3. **Add to main.py** (future enhancement):
   - Check retrain_frequency from config
   - Automatically retrain when time elapsed

## Next Steps

1. **Run initial retraining**: `python retrain_models.py`
2. **Check performance**: Review logs for R² and RMSE
3. **Compare results**: Note improvements vs old models
4. **Set schedule**: Plan regular retraining
5. **Monitor**: Track model performance over time

## Summary

The retraining script provides:
- ✅ Enhanced model parameters (stronger defaults)
- ✅ More training data (2000+ candles)
- ✅ Per-symbol or combined training
- ✅ Performance metrics and logging
- ✅ Easy command-line interface

**Run it regularly to keep your models strong and accurate!**

