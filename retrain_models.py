"""
Model Retraining Script - Strengthen and retrain models with improved parameters.

This script:
- Collects more historical data (2000+ candles)
- Trains models with stronger hyperparameters
- Supports per-symbol or combined training
- Saves models with performance metrics
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from datetime import datetime

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from utils.logger import setup_logger
from utils.helpers import load_config
from data_collection.binance_client import BinanceClient
from feature_engineering.technical_indicators import TechnicalIndicators
from feature_engineering.market_features import MarketFeatures
from feature_engineering.sentiment_features import SentimentAnalyzer
from models.model_trainer import ModelTrainer
from models.model_selector import ModelSelector

load_dotenv()
logger = setup_logger(__name__, log_file="logs/retrain_models.log")


class ModelRetrainer:
    """Enhanced model retraining with improved parameters."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize retrainer."""
        self.config = load_config(config_path)
        
        # Initialize Binance client
        api_key = os.getenv('BINANCE_API_KEY', self.config['binance']['api_key'])
        api_secret = os.getenv('BINANCE_API_SECRET', self.config['binance']['api_secret'])
        
        self.binance_client = BinanceClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=self.config['binance']['testnet']
        )
        
        # Initialize feature engineering
        self.technical_indicators = TechnicalIndicators()
        self.market_features = MarketFeatures(self.binance_client)
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # Model trainer with improved parameters
        # Initialize ModelTrainer with feature selection and hyperparameter tuning
        model_config = self.config.get('models', {})
        hyperparameter_config = model_config.get('hyperparameter_tuning', {})
        
        self.model_trainer = ModelTrainer(
            models_dir="models",
            use_feature_selection=model_config.get('use_feature_selection', True),
            feature_selection_method=model_config.get('feature_selection_method', 'combined'),
            use_hyperparameter_tuning=hyperparameter_config.get('enabled', True),
            n_tuning_trials=hyperparameter_config.get('n_trials', 100)
        )
        
    def collect_enhanced_data(self, symbol: str, lookback: int = 2000) -> pd.DataFrame:
        """
        Collect enhanced historical data for training.
        
        Args:
            symbol: Trading pair symbol
            lookback: Number of candles to collect
        
        Returns:
            DataFrame with features
        """
        logger.info(f"Collecting {lookback} candles for {symbol}...")
        
        # Collect market data
        klines = self.binance_client.get_klines(
            symbol=symbol,
            interval="1h",  # Use 1h for good balance
            limit=lookback,
            futures=False
        )
        
        if klines.empty:
            logger.warning(f"No data collected for {symbol}")
            return pd.DataFrame()
        
        logger.info(f"Collected {len(klines)} candles for {symbol}")
        
        # Engineer features
        df = self.technical_indicators.add_all_indicators(klines.copy())
        df = self.technical_indicators.add_custom_indicators(df)
        
        # Add market features
        try:
            order_book = self.market_features.get_order_book_features(symbol)
            for key, value in order_book.items():
                df[key] = value
        except:
            # Use defaults if order book unavailable
            df['order_book_imbalance'] = 0.0
            df['bid_volume'] = 0.0
            df['ask_volume'] = 0.0
            df['spread'] = 0.0
            df['spread_pct'] = 0.0
            df['weighted_mid_price'] = df['close']
            df['depth_1pct_bid'] = 0.0
            df['depth_1pct_ask'] = 0.0
        
        try:
            futures_features = self.market_features.get_futures_features(symbol)
            for key, value in futures_features.items():
                df[key] = value
        except:
            df['funding_rate'] = 0.0
            df['open_interest'] = 0.0
            df['long_short_ratio'] = 1.0
        
        # Add sentiment features (use defaults for historical)
        df['news_sentiment'] = 0.0
        df['news_polarity'] = 0.0
        df['news_volume'] = 0.0
        df['combined_sentiment'] = 0.0
        df['exchange_net_flow'] = 0.0
        
        # Create target variable
        prediction_horizon = self.config['prediction']['prediction_horizon']
        if prediction_horizon == '1h':
            periods = 1
        elif prediction_horizon == '4h':
            periods = 4
        else:
            periods = 1
        
        df['future_price'] = df['close'].shift(-periods)
        df['future_return'] = (df['future_price'] - df['close']) / df['close']
        
        # Remove rows with NaN target
        df = df.dropna(subset=['future_return'])
        df = df.fillna(0)
        
        logger.info(f"Engineered {len(df)} feature rows for {symbol}")
        return df
    
    def train_models_enhanced(
        self,
        features_df: pd.DataFrame,
        symbol: str = None,
        per_symbol: bool = False
    ) -> dict:
        """
        Train models with enhanced parameters.
        
        Args:
            features_df: Feature dataframe
            symbol: Optional symbol name for per-symbol training
            per_symbol: If True, save models with symbol prefix
        
        Returns:
            Dictionary of training results
        """
        logger.info(f"\n{'='*60}")
        if symbol:
            logger.info(f"Training models for {symbol}")
        else:
            logger.info("Training models (combined data)")
        logger.info(f"{'='*60}")
        
        if features_df.empty:
            logger.error("No features available for training")
            return {}
        
        # Prepare data
        X_train, y_train, X_val, y_val, X_test, y_test = self.model_trainer.prepare_data(
            features_df,
            target_column='future_return',
            test_size=0.2
        )
        
        # Train models with enhanced parameters
        models_to_train = self.config['models']['models_to_train']
        
        # Override with enhanced parameters
        enhanced_params = {
            'xgboost': {
                'n_estimators': 500,  # Increased from 200
                'max_depth': 8,      # Increased from 6
                'learning_rate': 0.05,  # Decreased from 0.1 (better generalization)
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'min_child_weight': 3,  # Regularization
                'gamma': 0.1,           # Regularization
                'random_state': 42
            },
            'lightgbm': {
                'n_estimators': 500,
                'max_depth': 8,
                'learning_rate': 0.05,
                'num_leaves': 31,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'min_child_samples': 20,
                'random_state': 42
            },
            'catboost': {
                'iterations': 500,  # Increased from 200
                'depth': 8,        # Increased from 6
                'learning_rate': 0.05,
                'random_seed': 42,
                'verbose': False
            }
        }
        
        results = {}
        for model_name in models_to_train:
            if model_name == 'lstm':
                # Try to train LSTM if TensorFlow is available
                try:
                    model, scores = self.model_trainer.train_lstm(
                        X_train, y_train, X_test, y_test, X_val=X_val, y_val=y_val
                    )
                    if model is not None:
                        results[model_name] = (model, scores)
                        # Save LSTM model
                        if per_symbol and symbol:
                            model_path = self.model_trainer.models_dir / f"{symbol}_{model_name}.h5"
                        else:
                            model_path = self.model_trainer.models_dir / f"{model_name}.h5"
                        model.save(str(model_path))
                        logger.info(
                            f"Saved {model_name} to {model_path} | "
                            f"Test R²: {scores.get('test_r2', 0):.4f} | "
                            f"Test RMSE: {scores.get('test_rmse', 0):.6f}"
                        )
                    continue
                except ImportError:
                    logger.warning("LSTM requires TensorFlow. Install with: pip install tensorflow")
                    continue
                except Exception as e:
                    logger.warning(f"LSTM training failed: {e}")
                    continue
            
            try:
                # Use enhanced parameters if available
                params = enhanced_params.get(model_name)
                
                if model_name == 'xgboost':
                    model, scores = self.model_trainer.train_xgboost(
                        X_train, y_train, X_test, y_test, X_val=X_val, y_val=y_val, params=params
                    )
                elif model_name == 'lightgbm':
                    model, scores = self.model_trainer.train_lightgbm(
                        X_train, y_train, X_test, y_test, X_val=X_val, y_val=y_val, params=params
                    )
                elif model_name == 'catboost':
                    model, scores = self.model_trainer.train_catboost(
                        X_train, y_train, X_test, y_test, X_val=X_val, y_val=y_val, params=params
                    )
                elif model_name == 'random_forest':
                    model, scores = self.model_trainer.train_random_forest(
                        X_train, y_train, X_test, y_test
                    )
                elif model_name == 'gradient_boosting':
                    model, scores = self.model_trainer.train_gradient_boosting(
                        X_train, y_train, X_test, y_test, X_val=X_val, y_val=y_val
                    )
                else:
                    logger.warning(f"Unknown model: {model_name}")
                    continue
                
                results[model_name] = (model, scores)
                
                # Save model with symbol prefix if per-symbol training
                import joblib
                if per_symbol and symbol:
                    model_path = self.model_trainer.models_dir / f"{symbol}_{model_name}.pkl"
                else:
                    model_path = self.model_trainer.models_dir / f"{model_name}.pkl"
                
                joblib.dump(model, model_path)
                logger.info(
                    f"Saved {model_name} to {model_path} | "
                    f"Test R²: {scores.get('test_r2', 0):.4f} | "
                    f"Test RMSE: {scores.get('test_rmse', 0):.6f}"
                )
                
            except Exception as e:
                logger.error(f"Error training {model_name}: {e}")
                continue
        
        return results
    
    def retrain_all_symbols(self, per_symbol: bool = False, lookback: int = 2000):
        """
        Retrain models for all configured symbols.
        
        Args:
            per_symbol: If True, train separate models per symbol
            lookback: Number of historical candles to use
        """
        symbols = self.config['trading']['symbols']
        
        logger.info(f"Starting model retraining for {len(symbols)} symbols")
        logger.info(f"Mode: {'Per-symbol' if per_symbol else 'Combined'}")
        logger.info(f"Lookback: {lookback} candles")
        
        if per_symbol:
            # Train separate models for each symbol
            for symbol in symbols:
                try:
                    features_df = self.collect_enhanced_data(symbol, lookback)
                    if not features_df.empty:
                        self.train_models_enhanced(features_df, symbol=symbol, per_symbol=True)
                except Exception as e:
                    logger.error(f"Error training {symbol}: {e}")
                    continue
        else:
            # Combine data from all symbols
            all_features = []
            for symbol in symbols:
                try:
                    features_df = self.collect_enhanced_data(symbol, lookback)
                    if not features_df.empty:
                        all_features.append(features_df)
                        logger.info(f"Collected {len(features_df)} samples from {symbol}")
                except Exception as e:
                    logger.error(f"Error collecting data for {symbol}: {e}")
                    continue
            
            if all_features:
                combined_df = pd.concat(all_features, ignore_index=True)
                logger.info(f"Total combined samples: {len(combined_df)}")
                self.train_models_enhanced(combined_df, per_symbol=False)
            else:
                logger.error("No data collected from any symbol!")
    
    def retrain_single_symbol(self, symbol: str, lookback: int = 2000):
        """
        Retrain models for a single symbol.
        
        Args:
            symbol: Trading pair symbol
            lookback: Number of historical candles to use
        """
        logger.info(f"Retraining models for {symbol}...")
        features_df = self.collect_enhanced_data(symbol, lookback)
        
        if not features_df.empty:
            results = self.train_models_enhanced(features_df, symbol=symbol, per_symbol=True)
            
            # Print summary
            logger.info(f"\n{'='*60}")
            logger.info(f"Training Summary for {symbol}")
            logger.info(f"{'='*60}")
            for model_name, (model, scores) in results.items():
                logger.info(
                    f"{model_name:20s} | "
                    f"R²: {scores.get('test_r2', 0):.4f} | "
                    f"RMSE: {scores.get('test_rmse', 0):.6f} | "
                    f"MAE: {scores.get('test_mae', 0):.6f}"
                )
        else:
            logger.error(f"No data available for {symbol}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Retrain trading models with enhanced parameters")
    parser.add_argument(
        '--symbol',
        type=str,
        help='Train models for a specific symbol (e.g., BTCUSDT)'
    )
    parser.add_argument(
        '--per-symbol',
        action='store_true',
        help='Train separate models for each symbol'
    )
    parser.add_argument(
        '--lookback',
        type=int,
        default=2000,
        help='Number of historical candles to use (default: 2000)'
    )
    
    args = parser.parse_args()
    
    retrainer = ModelRetrainer()
    
    if args.symbol:
        # Train single symbol
        retrainer.retrain_single_symbol(args.symbol, lookback=args.lookback)
    else:
        # Train all symbols
        retrainer.retrain_all_symbols(per_symbol=args.per_symbol, lookback=args.lookback)
    
    logger.info("\nModel retraining complete!")

