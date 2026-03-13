"""Main entry point for the Trading AI system."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict
import schedule
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from utils.logger import setup_logger
from utils.helpers import load_config
from data_collection.binance_client import BinanceClient
from data_collection.social_media import SocialMediaCollector
from data_collection.news_collector import NewsCollector
from data_collection.wallet_analyzer import WalletAnalyzer
from feature_engineering.technical_indicators import TechnicalIndicators
from feature_engineering.market_features import MarketFeatures
from feature_engineering.sentiment_features import SentimentAnalyzer
from models.model_trainer import ModelTrainer
from models.model_selector import ModelSelector
from models.predictors import PricePredictor
from trading.risk_manager import RiskManager
from trading.strategy import TradingStrategy
from trading.executor import TradeExecutor
from db.session import create_engine_from_config, get_sessionmaker

# Load environment variables
load_dotenv()

logger = setup_logger(__name__, log_file="logs/trading_ai.log")


class TradingAI:
    """Main Trading AI orchestrator."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize Trading AI system."""
        self.config = load_config(config_path)
        
        # Initialize components
        self._initialize_components()
        
        logger.info("Trading AI system initialized")
    
    def _initialize_components(self):
        """Initialize all system components."""
        # Binance client
        api_key = os.getenv('BINANCE_API_KEY', self.config['binance']['api_key'])
        api_secret = os.getenv('BINANCE_API_SECRET', self.config['binance']['api_secret'])
        
        self.binance_client = BinanceClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=self.config['binance']['testnet']
        )
        # Fail fast if API key / permissions / IP are invalid for this mode
        trading_mode = self.config['trading']['mode']
        self.binance_client.validate_for_mode(trading_mode)
        
        # Data collectors
        self.social_collector = SocialMediaCollector(
            twitter_config=self.config['data_collection']['social_media'].get('twitter', {}),
            reddit_config=self.config['data_collection']['social_media'].get('reddit', {})
        )
        
        self.news_collector = NewsCollector(
            sources=self.config['data_collection']['news'].get('sources', [])
        )
        
        self.wallet_analyzer = WalletAnalyzer()
        
        # Feature engineering
        self.technical_indicators = TechnicalIndicators()
        self.market_features = MarketFeatures(self.binance_client)
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # Models (will be loaded/trained)
        # Get feature selection and tuning settings from config
        model_config = self.config.get('models', {})
        hyperparameter_config = model_config.get('hyperparameter_tuning', {})
        
        self.model_trainer = ModelTrainer(
            use_feature_selection=model_config.get('use_feature_selection', True),
            feature_selection_method=model_config.get('feature_selection_method', 'combined'),
            use_hyperparameter_tuning=hyperparameter_config.get('enabled', True),
            n_tuning_trials=hyperparameter_config.get('n_trials', 100)
        )
        self.model_selector = None
        self.predictor = None
        
        # Trading (must be initialized before loading models)
        self.risk_manager = RiskManager(self.config['trading'])
        self.strategy = None
        
        # Try to load existing models from disk first (after risk_manager is initialized)
        self._load_existing_models()

        # Database (optional persistence)
        db_config = self.config.get("database", {})
        try:
            engine = create_engine_from_config(db_config)
            session_factory = get_sessionmaker(engine)
        except Exception as e:
            logger.error(f"Failed to initialize database engine, running without DB: {e}")
            session_factory = None

        self.executor = TradeExecutor(self.binance_client, self.risk_manager, db_session_factory=session_factory)
        
        # Link executor to risk manager for position checks
        self.risk_manager.executor = self.executor
    
    def collect_data(self, symbol: str) -> Dict:
        """
        Collect all data for a symbol.
        
        Args:
            symbol: Trading pair symbol
        
        Returns:
            Dictionary with all collected data
        """
        logger.info(f"Collecting data for {symbol}")
        
        data = {}
        
        # Market data
        intervals = self.config['data_collection']['market_data']['intervals']
        for interval in intervals:
            klines = self.binance_client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=1000,
                futures=False
            )
            data[f'market_{interval}'] = klines
        
        # Social media
        search_terms = self.config['data_collection']['social_media']['twitter'].get('search_terms', [])
        twitter_data = self.social_collector.collect_twitter_data(
            search_terms=search_terms,
            max_tweets=100
        )
        data['twitter'] = twitter_data
        
        subreddits = self.config['data_collection']['social_media'].get('reddit', {}).get('subreddits', [])
        reddit_data = self.social_collector.collect_reddit_data(
            subreddits=subreddits,
            max_posts=50
        )
        data['reddit'] = reddit_data
        
        # News
        news_data = self.news_collector.collect_news(max_articles=50)
        data['news'] = news_data
        
        # Wallet analysis
        wallet_data = self.wallet_analyzer.analyze_exchange_flows(symbol)
        data['wallet'] = wallet_data
        
        return data
    
    def engineer_features(self, data: Dict, symbol: str) -> pd.DataFrame:
        """
        Engineer features from collected data.
        
        Args:
            data: Collected data dictionary
            symbol: Trading pair symbol
        
        Returns:
            Feature dataframe
        """
        logger.info(f"Engineering features for {symbol}")
        
        # Start with main market data (1h interval)
        main_df = data.get('market_4h', pd.DataFrame())
        
        if main_df.empty:
            logger.warning("No market data available")
            return pd.DataFrame()
        
        # Add technical indicators
        main_df = self.technical_indicators.add_all_indicators(main_df)
        main_df = self.technical_indicators.add_custom_indicators(main_df)
        
        # Add market features
        order_book_features = self.market_features.get_order_book_features(symbol)
        for key, value in order_book_features.items():
            main_df[key] = value
        
        # Add futures features if available
        futures_features = self.market_features.get_futures_features(symbol)
        for key, value in futures_features.items():
            main_df[key] = value
        
        # Add sentiment features
        sentiment_features = self.sentiment_analyzer.calculate_sentiment_features(
            data.get('twitter', pd.DataFrame()),
            data.get('reddit', pd.DataFrame()),
            data.get('news', pd.DataFrame()),
            symbol
        )
        for key, value in sentiment_features.items():
            main_df[key] = value
        
        # Add wallet features
        wallet_data = data.get('wallet', {})
        main_df['exchange_net_flow'] = wallet_data.get('net_flow', 0.0)
        
        # Create target variable (future return)
        prediction_horizon = self.config['prediction']['prediction_horizon']
        if prediction_horizon == '1h':
            periods = 1
        elif prediction_horizon == '4h':
            periods = 4
        else:
            periods = 1
        
        main_df['future_price'] = main_df['close'].shift(-periods)
        main_df['future_return'] = (main_df['future_price'] - main_df['close']) / main_df['close']
        
        # Remove rows with NaN target
        main_df = main_df.dropna(subset=['future_return'])
        
        # Fill remaining NaN
        main_df = main_df.fillna(0)
        
        return main_df
    
    def _load_existing_models(self):
        """Try to load existing models from disk before training."""
        try:
            # Only load models specified in config
            models_to_train = self.config.get('models', {}).get('models_to_train', [])
            # Filter out commented models (those starting with #)
            models_to_load = [m.strip() for m in models_to_train if isinstance(m, str) and not m.strip().startswith('#')]
            
            loaded = self.model_trainer.load_models_from_disk(models_to_load=models_to_load)
            if loaded:
                # Create model selector with loaded models
                self.model_selector = ModelSelector(
                    self.model_trainer.models,
                    self.model_trainer.model_scores,
                    feature_names=self.model_trainer.feature_names
                )
                
                # Create predictor
                self.predictor = PricePredictor(
                    self.model_selector,
                    prediction_horizon=self.config['prediction']['prediction_horizon'],
                    confidence_threshold=self.config['prediction']['confidence_threshold']
                )
                
                # Create strategy
                self.strategy = TradingStrategy(
                    self.predictor,
                    self.risk_manager,
                    self.config
                )
                
                logger.info("Loaded existing models from disk")
                return True
        except Exception as e:
            logger.warning(f"Error loading existing models: {e}")
        
        return False
    
    def reload_models(self):
        """
        Reload models from disk (useful after manual retraining).
        This allows you to retrain models while bot is running.
        """
        logger.info("Reloading models from disk...")
        
        try:
            # Only load models specified in config
            models_to_train = self.config.get('models', {}).get('models_to_train', [])
            # Filter out commented models (those starting with #)
            models_to_load = [m.strip() for m in models_to_train if isinstance(m, str) and not m.strip().startswith('#')]
            
            # Load models
            loaded = self.model_trainer.load_models_from_disk(models_to_load=models_to_load)
            
            if loaded:
                # Recreate model selector with new models
                self.model_selector = ModelSelector(
                    self.model_trainer.models,
                    self.model_trainer.model_scores,
                    feature_names=self.model_trainer.feature_names
                )
                
                # Recreate predictor
                self.predictor = PricePredictor(
                    self.model_selector,
                    prediction_horizon=self.config['prediction']['prediction_horizon'],
                    confidence_threshold=self.config['prediction']['confidence_threshold'],
                    config=self.config
                )
                
                # Recreate strategy
                self.strategy = TradingStrategy(
                    self.predictor,
                    self.risk_manager,
                    self.config
                )
                
                logger.info("Models reloaded successfully!")
                return True
            else:
                logger.warning("No models found to reload")
                return False
        except Exception as e:
            logger.error(f"Error reloading models: {e}")
            return False
    
    def train_models(self, features_df: pd.DataFrame):
        """
        Train all models.
        
        Args:
            features_df: Feature dataframe with target
        """
        logger.info("Training models...")
        
        # Prepare data
        X_train, y_train, X_val, y_val, X_test, y_test = self.model_trainer.prepare_data(
            features_df,
            target_column='future_return'
        )
        
        # Train models
        models_to_train = self.config['models']['models_to_train']
        results = self.model_trainer.train_all_models(
            X_train, y_train, X_test, y_test,
            X_val=X_val, y_val=y_val,
            models_to_train=models_to_train
        )
        
        # Create model selector with feature names for alignment
        self.model_selector = ModelSelector(
            self.model_trainer.models,
            self.model_trainer.model_scores,
            feature_names=self.model_trainer.feature_names
        )
        
        # Create predictor
        self.predictor = PricePredictor(
            self.model_selector,
            prediction_horizon=self.config['prediction']['prediction_horizon'],
            confidence_threshold=self.config['prediction']['confidence_threshold'],
            config=self.config
        )
        
        # Create strategy
        self.strategy = TradingStrategy(
            self.predictor,
            self.risk_manager,
            self.config
        )
        
        logger.info("Models trained and strategy initialized")
    
    def run_trading_cycle(self, symbol: str):
        """
        Run one trading cycle for a symbol.
        
        Args:
            symbol: Trading pair symbol
        """
        try:
            logger.info(f"Running trading cycle for {symbol}")

            # Sync positions from exchange (reconnect / persistence support)
            self.executor.update_positions()
            
            # Collect data
            data = self.collect_data(symbol)
            
            # Engineer features
            features_df = self.engineer_features(data, symbol)
            
            if features_df.empty:
                logger.warning(f"No features available for {symbol}")
                return
            
            # Get latest features
            latest_features = features_df.iloc[-1:].drop(columns=['future_return', 'future_price'], errors='ignore')
            
            # Get current price
            ticker = self.binance_client.get_ticker(symbol)
            current_price = float(ticker.get('lastPrice', 0))
            
            if current_price == 0:
                logger.error(f"Could not get current price for {symbol}")
                return
            
            # Get account balances for spot and futures separately
            spot_balances = self.binance_client.get_account_balance(futures=False)
            spot_usdt = float(
                spot_balances.get('USDT', {}).get('free', 0)
                if isinstance(spot_balances.get('USDT'), dict)
                else spot_balances.get('USDT', 0) or 0
            )

            futures_balances = self.binance_client.get_account_balance(futures=True)
            futures_usdt = float(futures_balances.get('USDT', 0) or 0)

            trading_mode = self.config['trading']['mode']

            # At least one of the wallets should have usable balance
            if trading_mode in ['spot', 'both'] and spot_usdt <= 0 and trading_mode != 'futures':
                logger.warning("No USDT spot balance available for spot trading")
            if trading_mode in ['futures', 'both'] and futures_usdt <= 0 and trading_mode != 'spot':
                logger.warning("No USDT futures balance available for futures trading")
                if trading_mode == 'futures':
                    return

            # Generate signal(s) based on configured trading mode
            if trading_mode in ['spot', 'both'] and spot_usdt > 0:
                signal = self.strategy.generate_signal(
                    latest_features,
                    current_price,
                    spot_usdt,
                    symbol,
                    futures=False
                )
                
                if signal:
                    result = self.executor.execute_signal(signal)
                    if result:
                        logger.info(f"Spot trade executed: {result}")
            
            if trading_mode in ['futures', 'both'] and futures_usdt > 0:
                signal = self.strategy.generate_signal(
                    latest_features,
                    current_price,
                    futures_usdt,
                    symbol,
                    futures=True
                )
                
                if signal:
                    result = self.executor.execute_signal(signal)
                    if result:
                        logger.info(f"Futures trade executed: {result}")
            
            # Check existing positions
            self._manage_positions(symbol, latest_features, current_price)
            
        except Exception as e:
            logger.error(f"Error in trading cycle for {symbol}: {e}")
    
    def _manage_positions(self, symbol: str, features: pd.DataFrame, current_price: float):
        """
        Manage existing positions (including partial exits and dynamic order adjustment).
        
        This method:
        1. Checks for exit conditions (TP/SL hits)
        2. Updates trailing stops and adjusts SL orders on exchange
        3. Monitors TP order fills
        """
        positions = self.executor.get_active_positions()
        
        for position in positions:
            if position['symbol'] == symbol:
                # Check exit conditions and update trailing stops
                should_exit, reason = self.strategy.should_exit_position(
                    position,
                    current_price,
                    features
                )
                
                if should_exit:
                    result = self.executor.close_position(position, reason)
                    if result and result.get('success'):
                        # If partial exit, position is still active with updated remaining_size
                        # If full exit, position was removed from active_positions
                        logger.info(f"Position exit executed: {reason}")
                else:
                    # Position still active - trailing stop may have been updated
                    # The update_stop_loss_order is called from within should_exit_position
                    # when trailing stop moves, so we don't need to do anything else here
                    pass
    
    def run(self):
        """Run the trading AI system."""
        logger.info("Starting Trading AI system")
        
        symbols = self.config['trading']['symbols']
        
        # Initial model loading/training
        # Try to load existing models first, otherwise train new ones
        if not self.model_selector:
            logger.info("No existing models found, performing initial model training...")
            for symbol in symbols:
                data = self.collect_data(symbol)
                features_df = self.engineer_features(data, symbol)
                
                if not features_df.empty:
                    self.train_models(features_df)
                    break  # Train on first symbol
        else:
            logger.info("Using existing models from disk")
        
        # Track last retraining time
        self.last_retrain_time = datetime.now()
        retrain_frequency = self.config['models'].get('retrain_frequency', 86400)  # Default 24 hours
        
        # Schedule trading cycles
        update_frequency = self.config['data_collection']['market_data']['update_frequency']
        max_workers = self.config.get('trading', {}).get('max_concurrent_symbols', len(symbols))
        
        def trading_job():
            """Process all symbols concurrently."""
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all symbols for concurrent processing
                future_to_symbol = {
                    executor.submit(self.run_trading_cycle, symbol): symbol
                    for symbol in symbols
                }
                
                # Process completed tasks
                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        future.result()  # This will raise any exceptions that occurred
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
        
        def retrain_job():
            """Automatic model retraining job."""
            time_since_retrain = (datetime.now() - self.last_retrain_time).total_seconds()
            
            if time_since_retrain >= retrain_frequency:
                logger.info(f"Automatic retraining triggered (last retrain: {time_since_retrain/3600:.1f} hours ago)")
                
                try:
                    # Collect fresh data and retrain
                    for symbol in symbols:
                        logger.info(f"Collecting data for retraining from {symbol}...")
                        data = self.collect_data(symbol)
                        features_df = self.engineer_features(data, symbol)
                        
                        if not features_df.empty:
                            logger.info(f"Retraining models with {len(features_df)} samples...")
                            self.train_models(features_df)
                            self.last_retrain_time = datetime.now()
                            logger.info("Model retraining complete! Models updated in memory.")
                            break
                except Exception as e:
                    logger.error(f"Error during automatic retraining: {e}")
        
        def reload_models_job():
            """Check for and reload models from disk (for manual retraining)."""
            try:
                # Check if models were updated (compare file modification times)
                model_path = self.model_trainer.models_dir / "xgboost.pkl"
                if model_path.exists():
                    file_time = datetime.fromtimestamp(model_path.stat().st_mtime)
                    # Reload if file was modified in last 5 minutes (manual retraining window)
                    if (datetime.now() - file_time).total_seconds() < 300:
                        logger.info("Detected new models on disk, reloading...")
                        self.reload_models()
            except Exception as e:
                logger.debug(f"Model reload check: {e}")
        
        # Schedule periodic execution
        schedule.every(update_frequency).seconds.do(trading_job)
        
        # Schedule retraining check (check every hour)
        schedule.every(3600).seconds.do(retrain_job)
        
        # Schedule model reload check (check every 5 minutes for manual retraining)
        schedule.every(300).seconds.do(reload_models_job)
        
        logger.info(f"Trading AI running. Update frequency: {update_frequency} seconds")
        logger.info(f"Automatic retraining: Every {retrain_frequency/3600:.1f} hours (checks every hour)")
        logger.info("Model reload: Checks every 5 minutes for manually retrained models")
        
        # Run main loop
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Trading AI stopped by user")


if __name__ == "__main__":
    trading_ai = TradingAI()
    trading_ai.run()

