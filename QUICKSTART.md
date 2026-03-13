# Quick Start Guide

## Getting Started in 5 Minutes

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Set Up API Credentials

1. **Get Binance API Keys**:
   - Go to [Binance API Management](https://www.binance.com/en/my/settings/api-management)
   - Create API key and secret
   - For testing, use testnet: [Binance Testnet](https://testnet.binance.vision/)

2. **Create `.env` file**:
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env`** with your credentials:
   ```env
   BINANCE_API_KEY=your_key_here
   BINANCE_API_SECRET=your_secret_here
   ```

### Step 3: Configure Settings

Edit `config/config.yaml`:

```yaml
binance:
  testnet: true  # Start with testnet!

trading:
  symbols:
    - "BTCUSDT"  # Start with one symbol
  mode: "futures"   # Options: "spot", "futures", "both"
  
  # Risk settings (adjust to your risk tolerance)
  risk:
    risk_per_trade: 0.015  # 1.5% risk per trade
    max_position_size: 0.05  # 5% max position
    confidence_threshold: 0.65  # Minimum confidence (lower = more trades)

# Database (optional but recommended)
database:
  type: "sqlite"
  path: "data/trading_data.db"
```

### Step 4: Run the System

```bash
python main.py
```

The system will:
1. Collect market data
2. Train models (first run takes a few minutes)
3. Start generating trading signals
4. Execute trades (on testnet)

## Understanding the Output

### Console Output
```
INFO - Collecting data for BTCUSDT
INFO - Engineering features for BTCUSDT
INFO - Training models...
INFO - XGBoost - Test RMSE: 0.001234, R²: 0.8567
INFO - Signal generated: LONG BTCUSDT | Entry: 45000.00 | SL: 44100.00 | TP: 47700.00
```

### Log Files
Check `logs/trading_ai.log` for detailed information.

## Testing Without Trading

To test the system without executing trades:

1. Set `testnet: true` in config
2. Use a testnet account with test funds
3. Monitor signals without executing (modify `executor.py` to log only)

## Common Issues

### "No module named 'binance'"
```bash
pip install python-binance
```

### "API key invalid"
- Check your `.env` file
- Verify API key permissions (enable trading)
- For testnet, use testnet API keys

### "No features available"
- Check internet connection
- Verify Binance API is accessible
- Check symbol names are correct (e.g., "BTCUSDT" not "BTC/USDT")

### Models not training
- Ensure sufficient historical data (at least 1000 candles)
- Check feature engineering is working
- Review logs for errors

## Next Steps

1. **Monitor Performance**: Watch trades and model predictions
2. **Adjust Risk Parameters**: 
   - Lower `confidence_threshold` (e.g., 0.50) for more trades
   - Adjust `risk_per_trade` and `max_position_size` for position sizing
   - See `TRADING_AGGRESSIVENESS_CONTROLS.md` for detailed controls
3. **Add More Symbols**: Add to `trading.symbols` in config
4. **Enable Futures**: Set `mode: "futures"` or `"both"` when ready
5. **Configure Database**: Set up SQLite (default) or PostgreSQL for position persistence
6. **Add Social Media**: Configure Twitter/Reddit APIs for sentiment (optional)
7. **Review Trading Rules**: Read `RULES_OF_THE_GAME.md` to understand profit-taking and exits

## Safety Checklist

Before live trading:
- [ ] Tested on testnet for at least 1 week
- [ ] Verified all risk parameters
- [ ] Set appropriate position sizes
- [ ] Enabled daily loss limits
- [ ] Reviewed and understood all code
- [ ] Have emergency stop procedure
- [ ] Only risk capital you can afford to lose

## Getting Help

1. Check `logs/trading_ai.log` for errors
2. Review `ARCHITECTURE.md` for system details
3. Verify configuration in `config/config.yaml`
4. Test API connectivity separately

## Example: Manual Testing

Test data collection:
```python
from src.data_collection.binance_client import BinanceClient
import os
from dotenv import load_dotenv

load_dotenv()
client = BinanceClient(
    os.getenv('BINANCE_API_KEY'),
    os.getenv('BINANCE_API_SECRET'),
    testnet=True
)

# Get market data
df = client.get_klines('BTCUSDT', '1h', limit=100)
print(df.head())
```

Test feature engineering:
```python
from src.feature_engineering.technical_indicators import TechnicalIndicators

indicators = TechnicalIndicators()
df_with_features = indicators.add_all_indicators(df)
print(df_with_features.columns)
```

## Performance Tips

1. **Start Small**: Use small position sizes initially
2. **Monitor Closely**: Watch the first few trades
3. **Adjust Parameters**: Fine-tune based on results
4. **Regular Retraining**: Models should be retrained periodically
5. **Data Quality**: Ensure good data collection

---

**Remember**: Always test thoroughly before live trading!

