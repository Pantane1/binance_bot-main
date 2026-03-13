# Trading AI Architecture Documentation

## System Overview

The Trading AI system is a modular, production-ready cryptocurrency trading platform that combines machine learning predictions with comprehensive risk management. The system is designed to be accurate, safe, and extensible.

## Architecture Layers

### 1. Data Collection Layer

**Purpose**: Gather data from multiple sources to inform trading decisions.

#### Components:

1. **BinanceClient** (`src/data_collection/binance_client.py`)
   - Wraps Binance API for market data and trading
   - Supports both spot and futures markets
   - Handles rate limiting and error recovery
   - Key methods:
     - `get_klines()`: Historical price data
     - `get_order_book()`: Real-time order book
     - `get_funding_rate()`: Futures funding rates
     - `place_order()`: Execute trades
     - `get_account_balance()`: Account information

2. **SocialMediaCollector** (`src/data_collection/social_media.py`)
   - Twitter data collection via Tweepy
   - Reddit data collection via PRAW
   - Extracts cryptocurrency mentions
   - Tracks engagement metrics

3. **NewsCollector** (`src/data_collection/news_collector.py`)
   - RSS feed aggregation
   - Article content extraction
   - Crypto Fear & Greed Index integration
   - Multi-source news aggregation

4. **WalletAnalyzer** (`src/data_collection/wallet_analyzer.py`)
   - Exchange flow analysis
   - Whale movement detection
   - Accumulation/distribution scoring
   - Blockchain data integration (placeholder for API keys)

### 2. Feature Engineering Layer

**Purpose**: Transform raw data into predictive features.

#### Components:

1. **TechnicalIndicators** (`src/feature_engineering/technical_indicators.py`)
   - 20+ technical indicators
   - Momentum, trend, volatility, volume indicators
   - Custom indicators (VPT, MFI, price position)

2. **MarketFeatures** (`src/feature_engineering/market_features.py`)
   - Order book analysis (imbalance, depth, spread)
   - Futures-specific features (funding rate, OI)
   - Volume profile calculation
   - Liquidation level estimation

3. **SentimentAnalyzer** (`src/feature_engineering/sentiment_features.py`)
   - TextBlob sentiment analysis
   - Crypto-specific keyword analysis
   - Multi-source sentiment aggregation
   - Time-windowed sentiment features

### 3. Model Layer

**Purpose**: Train and deploy ML models for price prediction.

#### Components:

1. **ModelTrainer** (`src/models/model_trainer.py`)
   - Trains multiple ML models
   - Time series cross-validation
   - Model evaluation and comparison
   - Model persistence

2. **ModelSelector** (`src/models/model_selector.py`)
   - Ensemble prediction methods
   - Performance-based weighting
   - Confidence scoring
   - Best model selection

3. **PricePredictor** (`src/models/predictors.py`)
   - Orchestrates predictions
   - Calculates predicted returns
   - Direction determination (LONG/SHORT/HOLD)
   - Confidence filtering

### 4. Trading Layer

**Purpose**: Execute trades with risk management.

#### Components:

1. **RiskManager** (`src/trading/risk_manager.py`)
   - Position sizing calculations
   - Stop loss/take profit calculation
   - Daily loss limits
   - Liquidation protection
   - Trade validation

2. **TradingStrategy** (`src/trading/strategy.py`)
   - Signal generation
   - Combines predictions with risk management
   - Position exit logic
   - Multi-timeframe analysis

3. **TradeExecutor** (`src/trading/executor.py`)
   - Order execution
   - Position management (supports multiple positions per symbol)
   - Partial position closing (profit taking in chunks)
   - Position syncing from exchange on reconnect
   - Database persistence of positions and trades

## Data Flow

```
1. Data Collection
   ├── Market Data (Binance)
   ├── Social Media (Twitter, Reddit)
   ├── News Articles
   └── Wallet/Blockchain Data

2. Feature Engineering
   ├── Technical Indicators
   ├── Market Microstructure
   ├── Sentiment Features
   └── Wallet Features
   └── Combined Feature DataFrame

3. Model Prediction
   ├── Feature Input
   ├── Ensemble Prediction
   ├── Confidence Score
   └── Predicted Return/Direction

4. Risk Management
   ├── Position Sizing
   ├── Stop Loss/Take Profit
   ├── Liquidation Check
   └── Trade Validation

5. Execution
   ├── Signal Generation
   ├── Order Placement
   └── Position Management
```

## Risk Management Strategy

### Position Sizing
- **Kelly Criterion**: Optimal position sizing based on win rate and risk/reward
- **Volatility Adjustment**: Position size adjusted for market volatility
- **Maximum Position**: 10% of portfolio per trade

### Stop Loss & Take Profit
- **Risk/Reward Ratio**: 1:2 (default, more generous)
- **Stop Loss**: 1.5% from entry
- **Take Profit**: 3% from entry
- **Trailing Stops**: Enabled by default, activates after 1R profit, trails 1% behind peak
- **Partial Profit Taking**: Takes 50% at 1R, remaining 50% at 2R

### Liquidation Protection (Futures)
- **Buffer Requirement**: 6% minimum distance from liquidation (configurable)
- **Leverage Limits**: Maximum 15x leverage (configurable)
- **Real-time Monitoring**: Continuous checks
- **Position Syncing**: Automatically syncs positions from exchange on reconnect

### Daily Limits
- **Max Daily Loss**: 5% of account
- **Max Daily Trades**: Configurable
- **Automatic Shutdown**: Stops trading if limit reached

## Model Training Pipeline

1. **Data Collection**: Gather historical data
2. **Feature Engineering**: Create features
3. **Target Creation**: Calculate future returns
4. **Train/Test Split**: Time series split
5. **Model Training**: Train all specified models
6. **Evaluation**: Calculate metrics (RMSE, MAE, R²)
7. **Model Selection**: Choose best model or ensemble
8. **Persistence**: Save trained models

## Prediction Pipeline

1. **Feature Extraction**: Get latest features
2. **Model Prediction**: Run ensemble prediction
3. **Confidence Calculation**: Model agreement score
4. **Direction Determination**: LONG/SHORT/HOLD
5. **Risk Validation**: Check risk parameters
6. **Signal Generation**: Create trading signal

## Trading Execution Flow

1. **Signal Generation**: Strategy generates signal
2. **Risk Validation**: Risk manager validates
3. **Position Sizing**: Calculate position size
4. **Order Placement**: Execute on exchange
5. **Position Tracking**: Monitor active positions
6. **Exit Logic**: Stop loss, take profit, or signal reversal

## Configuration System

All configuration is centralized in `config/config.yaml`:

- **Trading Settings**: Symbols, mode, risk parameters
- **Data Collection**: Sources, frequencies, limits
- **Feature Engineering**: Indicators, features to use
- **Model Configuration**: Models to train, hyperparameters
- **Prediction Settings**: Horizon, confidence thresholds

## Error Handling

- **API Errors**: Graceful degradation, retry logic
- **Data Quality**: Missing data handling, validation
- **Model Errors**: Fallback to simpler models
- **Trading Errors**: Position validation, order confirmation

## Performance Optimization

- **Caching**: Feature caching for repeated calculations
- **Batch Processing**: Efficient data collection
- **Parallel Processing**: (Future) Multi-symbol parallel processing
- **Database**: SQLite (default) or PostgreSQL for persistent storage of positions, trades, and historical data
- **Position Management**: In-memory tracking with database persistence for continuity

## Security Considerations

1. **API Keys**: Stored in environment variables, never in code
2. **Testnet Default**: Uses testnet for safety
3. **Position Limits**: Prevents overexposure
4. **Daily Limits**: Prevents catastrophic losses
5. **Validation**: Multiple validation layers before execution

## Extensibility

The modular architecture allows easy extension:

- **New Data Sources**: Add to `data_collection/`
- **New Features**: Add to `feature_engineering/`
- **New Models**: Add to `models/model_trainer.py`
- **New Strategies**: Extend `trading/strategy.py`
- **New Exchanges**: Implement exchange client interface

## Monitoring & Logging

- **Structured Logging**: All components log to file and console
- **Trade Logging**: All trades logged with full details
- **Performance Metrics**: Model performance tracked
- **Risk Metrics**: Risk metrics calculated and logged

## Testing Strategy

1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Component interaction testing
3. **Backtesting**: Historical data testing
4. **Paper Trading**: Testnet trading
5. **Live Trading**: Small position sizes initially

## Recent Enhancements

- **Multi-position trading**: Support for multiple concurrent positions per symbol (pyramiding)
- **Partial profit taking**: Disciplined profit collection at specified R multiples
- **Trailing stops**: Dynamic stop loss that protects winners
- **Database persistence**: SQLite/PostgreSQL support for positions and trades
- **Position syncing**: Automatic detection and management of positions on reconnect
- **Improved risk/reward**: More generous 1:2 ratio with tighter stops for better win rates
- **Enhanced logging**: Detailed confidence threshold logging for better debugging

## Future Enhancements

- Deep learning models (LSTM, Transformer)
- Real-time blockchain data
- Advanced order types (stop-limit, OCO orders)
- Portfolio optimization
- Web dashboard
- Multi-exchange support
- Backtesting framework
- Model metadata tracking in database

