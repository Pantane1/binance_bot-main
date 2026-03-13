"""Model training and evaluation."""

import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb
import lightgbm as lgb
import catboost as cb
from typing import Dict, List, Tuple, Optional
import joblib
from pathlib import Path
from utils.logger import setup_logger
from models.feature_selector import FeatureSelector
from models.hyperparameter_tuner import HyperparameterTuner

logger = setup_logger(__name__)


class ModelTrainer:
    """Train and evaluate multiple ML models."""
    
    def __init__(
        self,
        models_dir: str = "models",
        use_feature_selection: bool = True,
        feature_selection_method: str = 'combined',
        use_hyperparameter_tuning: bool = True,
        n_tuning_trials: int = 100
    ):
        """
        Initialize model trainer.
        
        Args:
            models_dir: Directory to save trained models
            use_feature_selection: Whether to use feature selection
            feature_selection_method: Method for feature selection ('mutual_info', 'correlation', 'importance', 'combined')
            use_hyperparameter_tuning: Whether to use hyperparameter tuning
            n_tuning_trials: Number of trials for hyperparameter tuning
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.models = {}
        self.model_scores = {}
        self.feature_names = None  # Store feature names used during training
        
        # Feature selection
        self.use_feature_selection = use_feature_selection
        self.feature_selector = FeatureSelector(method=feature_selection_method) if use_feature_selection else None
        
        # Hyperparameter tuning
        self.use_hyperparameter_tuning = use_hyperparameter_tuning
        self.hyperparameter_tuner = HyperparameterTuner(n_trials=n_tuning_trials) if use_hyperparameter_tuning else None
    
    def load_models_from_disk(
        self,
        symbol: str = None,
        models_to_load: Optional[List[str]] = None
    ) -> Dict:
        """
        Load trained models from disk.
        
        Args:
            symbol: Optional symbol name for per-symbol models
            models_to_load: Optional list of model names to load (if None, loads all found)
        
        Returns:
            Dictionary of loaded models and scores
        """
        loaded_models = {}
        loaded_scores = {}
        
        # If models_to_load is specified, only load those; otherwise try all
        if models_to_load is None:
            model_names = ['xgboost', 'lightgbm', 'catboost', 'random_forest', 'gradient_boosting', 'lstm']
        else:
            model_names = models_to_load
        
        for model_name in model_names:
            try:
                if symbol:
                    # LSTM uses .h5 extension, others use .pkl
                    if model_name == 'lstm':
                        model_path = self.models_dir / f"{symbol}_{model_name}.h5"
                    else:
                        model_path = self.models_dir / f"{symbol}_{model_name}.pkl"
                else:
                    # LSTM uses .h5 extension, others use .pkl
                    if model_name == 'lstm':
                        model_path = self.models_dir / f"{model_name}.h5"
                    else:
                        model_path = self.models_dir / f"{model_name}.pkl"
                
                if model_path.exists():
                    if model_name == 'lstm':
                        # LSTM uses special loading
                        try:
                            from models.lstm_model import LSTMModel
                            model = LSTMModel.load(str(model_path))
                            loaded_models[model_name] = model
                            logger.info(f"Loaded {model_name} from {model_path}")
                        except ImportError:
                            logger.warning(f"LSTM requires TensorFlow. Install with: pip install tensorflow")
                        except Exception as e:
                            logger.warning(f"Could not load LSTM model: {e}")
                    else:
                        model = joblib.load(model_path)
                        loaded_models[model_name] = model
                        logger.info(f"Loaded {model_name} from {model_path}")
                else:
                    logger.debug(f"Model file not found: {model_path}")
            except Exception as e:
                logger.warning(f"Error loading {model_name}: {e}")
        
        if loaded_models:
            self.models = loaded_models
            # Create dummy scores (we don't store scores separately)
            for name in loaded_models.keys():
                loaded_scores[name] = {'test_r2': 0.0, 'test_rmse': 0.0}
            self.model_scores = loaded_scores
            
            # Try to extract feature names from loaded models
            try:
                first_model = list(loaded_models.values())[0]
                if hasattr(first_model, 'feature_names_in_'):
                    self.feature_names = list(first_model.feature_names_in_)
                elif hasattr(first_model, 'get_booster'):
                    # XGBoost
                    booster = first_model.get_booster()
                    self.feature_names = booster.feature_names
                elif hasattr(first_model, 'feature_name_'):
                    # LightGBM
                    self.feature_names = first_model.feature_name_
                logger.info(f"Extracted {len(self.feature_names) if self.feature_names else 0} feature names from loaded models")
            except Exception as e:
                logger.warning(f"Could not extract feature names from loaded models: {e}")
                self.feature_names = None
            
            logger.info(f"Loaded {len(loaded_models)} models from disk")
        else:
            logger.info("No models found on disk, will train new models")
        
        return loaded_models
    
    def prepare_data(
        self,
        df: pd.DataFrame,
        target_column: str = 'future_return',
        test_size: float = 0.2,
        validation_size: float = 0.1
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
        """
        Prepare data for training with validation set.
        
        Args:
            df: Feature dataframe
            target_column: Target variable column
            test_size: Proportion of data for testing
            validation_size: Proportion of training data for validation
        
        Returns:
            X_train, y_train, X_val, y_val, X_test, y_test
        """
        # Remove rows with NaN in target
        df = df.dropna(subset=[target_column])
        
        # Remove outliers in target (beyond 3 standard deviations)
        target_mean = df[target_column].mean()
        target_std = df[target_column].std()
        if target_std > 0:
            df = df[
                (df[target_column] >= target_mean - 3 * target_std) &
                (df[target_column] <= target_mean + 3 * target_std)
            ]
        
        # Separate features and target
        # Exclude target column and future_price (which is used to calculate target)
        exclude_cols = [target_column, 'future_price']
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        X = df[feature_cols].fillna(0)
        y = df[target_column]
        
        # Remove features with zero variance (constant features)
        feature_variance = X.var()
        non_zero_var_cols = feature_variance[feature_variance > 1e-8].index.tolist()
        X = X[non_zero_var_cols]
        
        if len(non_zero_var_cols) < len(feature_cols):
            logger.info(f"Removed {len(feature_cols) - len(non_zero_var_cols)} constant features")
        
        # Remove highly correlated features
        if self.feature_selector:
            X, _ = self.feature_selector.remove_correlated_features(X, threshold=0.95)
            logger.info(f"After removing correlated features: {len(X.columns)} features")
        
        # Apply feature selection if enabled
        if self.feature_selector and len(X.columns) > 20:
            X, selected_features, feature_scores = self.feature_selector.select_features(
                X, y, n_features=None  # Auto-select
            )
            self.feature_names = selected_features
            logger.info(f"Feature selection: {len(X.columns)} features selected from {len(non_zero_var_cols)}")
        else:
            # Store feature names for alignment during prediction
            self.feature_names = list(X.columns)
        
        # Time series split
        test_split_idx = int(len(X) * (1 - test_size))
        val_split_idx = int(test_split_idx * (1 - validation_size))
        
        X_train, X_val, X_test = X.iloc[:val_split_idx], X.iloc[val_split_idx:test_split_idx], X.iloc[test_split_idx:]
        y_train, y_val, y_test = y.iloc[:val_split_idx], y.iloc[val_split_idx:test_split_idx], y.iloc[test_split_idx:]
        
        logger.info(f"Training set: {len(X_train)}, Validation set: {len(X_val)}, Test set: {len(X_test)}")
        logger.info(f"Target stats - Mean: {y_train.mean():.6f}, Std: {y_train.std():.6f}, Range: [{y_train.min():.6f}, {y_train.max():.6f}]")
        
        return X_train, y_train, X_val, y_val, X_test, y_test
    
    def train_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        params: Optional[Dict] = None
    ) -> Tuple[xgb.XGBRegressor, Dict]:
        """Train XGBoost model with early stopping and optional hyperparameter tuning."""
        # Use hyperparameter tuning if enabled and validation set available
        if self.hyperparameter_tuner and X_val is not None and y_val is not None and params is None:
            logger.info("Tuning XGBoost hyperparameters...")
            params = self.hyperparameter_tuner.tune_xgboost(X_train, y_train, X_val, y_val)
        
        if params is None:
            params = {
                'n_estimators': 2000,  # Increased for early stopping
                'max_depth': 10,       # Increased depth
                'learning_rate': 0.1,   # Higher initial rate
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'min_child_weight': 1,  # Less restrictive
                'gamma': 0.0,          # Less regularization
                'reg_alpha': 0.1,      # L1 regularization
                'reg_lambda': 1.0,     # L2 regularization
                'random_state': 42
            }
        
        # Try to use early stopping if validation set is available
        # Handle different XGBoost versions with fallback
        model = xgb.XGBRegressor(**params)
        
        if X_val is not None and y_val is not None:
            # Try method 1: early_stopping_rounds in fit() (XGBoost < 2.0)
            try:
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    early_stopping_rounds=50,
                    verbose=False
                )
            except TypeError:
                # Try method 2: early_stopping_rounds in constructor (XGBoost 2.0+)
                try:
                    params_with_early_stop = params.copy()
                    params_with_early_stop['early_stopping_rounds'] = 50
                    model = xgb.XGBRegressor(**params_with_early_stop)
                    model.fit(
                        X_train, y_train,
                        eval_set=[(X_val, y_val)],
                        verbose=False
                    )
                except (TypeError, ValueError):
                    # Fallback: train without early stopping
                    logger.warning("XGBoost version doesn't support early stopping, training without it")
                    model = xgb.XGBRegressor(**params)
                    model.fit(X_train, y_train)
        else:
            model.fit(X_train, y_train)
        
        # Evaluate
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)
        
        scores = {
            'train_rmse': np.sqrt(mean_squared_error(y_train, train_pred)),
            'test_rmse': np.sqrt(mean_squared_error(y_test, test_pred)),
            'train_mae': mean_absolute_error(y_train, train_pred),
            'test_mae': mean_absolute_error(y_test, test_pred),
            'train_r2': r2_score(y_train, train_pred),
            'test_r2': r2_score(y_test, test_pred)
        }
        
        logger.info(f"XGBoost - Test RMSE: {scores['test_rmse']:.6f}, R²: {scores['test_r2']:.4f}")
        
        return model, scores
    
    def train_lightgbm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        params: Optional[Dict] = None
    ) -> Tuple[lgb.LGBMRegressor, Dict]:
        """Train LightGBM model with early stopping and optional hyperparameter tuning."""
        # Use hyperparameter tuning if enabled and validation set available
        if self.hyperparameter_tuner and X_val is not None and y_val is not None and params is None:
            logger.info("Tuning LightGBM hyperparameters...")
            params = self.hyperparameter_tuner.tune_lightgbm(X_train, y_train, X_val, y_val)
        
        if params is None:
            params = {
                'n_estimators': 2000,  # Increased for early stopping
                'max_depth': 10,       # Increased depth
                'learning_rate': 0.1,  # Higher initial rate
                'num_leaves': 127,     # More leaves for better fit
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'min_child_samples': 10,  # Less restrictive
                'reg_alpha': 0.1,     # L1 regularization
                'reg_lambda': 0.1,     # L2 regularization
                'random_state': 42,
                'verbose': -1
            }
        
        model = lgb.LGBMRegressor(**params)
        
        # Use validation set for early stopping if available
        if X_val is not None and y_val is not None:
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
            )
        else:
            model.fit(X_train, y_train)
        
        # Evaluate
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)
        
        scores = {
            'train_rmse': np.sqrt(mean_squared_error(y_train, train_pred)),
            'test_rmse': np.sqrt(mean_squared_error(y_test, test_pred)),
            'train_mae': mean_absolute_error(y_train, train_pred),
            'test_mae': mean_absolute_error(y_test, test_pred),
            'train_r2': r2_score(y_train, train_pred),
            'test_r2': r2_score(y_test, test_pred)
        }
        
        logger.info(f"LightGBM - Test RMSE: {scores['test_rmse']:.6f}, R²: {scores['test_r2']:.4f}")
        
        return model, scores
    
    def train_catboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        params: Optional[Dict] = None
    ) -> Tuple[cb.CatBoostRegressor, Dict]:
        """Train CatBoost model with early stopping and optional hyperparameter tuning."""
        # Use hyperparameter tuning if enabled and validation set available
        if self.hyperparameter_tuner and X_val is not None and y_val is not None and params is None:
            logger.info("Tuning CatBoost hyperparameters...")
            params = self.hyperparameter_tuner.tune_catboost(X_train, y_train, X_val, y_val)
        
        if params is None:
            params = {
                'iterations': 2000,  # Increased for early stopping
                'depth': 8,          # Increased depth
                'learning_rate': 0.1,  # Higher initial rate
                'l2_leaf_reg': 3.0,   # L2 regularization
                'random_seed': 42,
                'verbose': False
            }
        
        model = cb.CatBoostRegressor(**params)
        
        # Use validation set for early stopping if available
        if X_val is not None and y_val is not None:
            model.fit(
                X_train, y_train,
                eval_set=(X_val, y_val),
                early_stopping_rounds=50,
                verbose=False
            )
        else:
            model.fit(X_train, y_train)
        
        # Evaluate
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)
        
        scores = {
            'train_rmse': np.sqrt(mean_squared_error(y_train, train_pred)),
            'test_rmse': np.sqrt(mean_squared_error(y_test, test_pred)),
            'train_mae': mean_absolute_error(y_train, train_pred),
            'test_mae': mean_absolute_error(y_test, test_pred),
            'train_r2': r2_score(y_train, train_pred),
            'test_r2': r2_score(y_test, test_pred)
        }
        
        logger.info(f"CatBoost - Test RMSE: {scores['test_rmse']:.6f}, R²: {scores['test_r2']:.4f}")
        
        return model, scores
    
    def train_random_forest(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        params: Optional[Dict] = None
    ) -> Tuple[RandomForestRegressor, Dict]:
        """Train Random Forest model."""
        if params is None:
            params = {
                'n_estimators': 300,  # Increased for better performance
                'max_depth': 12,      # Increased depth
                'min_samples_split': 5,  # Regularization
                'min_samples_leaf': 2,   # Regularization
                'random_state': 42,
                'n_jobs': -1
            }
        
        model = RandomForestRegressor(**params)
        model.fit(X_train, y_train)
        
        # Evaluate
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)
        
        scores = {
            'train_rmse': np.sqrt(mean_squared_error(y_train, train_pred)),
            'test_rmse': np.sqrt(mean_squared_error(y_test, test_pred)),
            'train_mae': mean_absolute_error(y_train, train_pred),
            'test_mae': mean_absolute_error(y_test, test_pred),
            'train_r2': r2_score(y_train, train_pred),
            'test_r2': r2_score(y_test, test_pred)
        }
        
        logger.info(f"Random Forest - Test RMSE: {scores['test_rmse']:.6f}, R²: {scores['test_r2']:.4f}")
        
        return model, scores
    
    def train_gradient_boosting(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        params: Optional[Dict] = None
    ) -> Tuple[GradientBoostingRegressor, Dict]:
        """Train Gradient Boosting model with early stopping."""
        if params is None:
            params = {
                'n_estimators': 500,  # Will use early stopping
                'max_depth': 6,       # Moderate depth to prevent overfitting
                'learning_rate': 0.1,  # Higher rate for faster convergence
                'min_samples_split': 10,  # More regularization
                'min_samples_leaf': 5,    # More regularization
                'subsample': 0.8,     # Stochastic gradient boosting
                'max_features': 'sqrt',  # Feature subsampling
                'validation_fraction': 0.1,  # For early stopping
                'n_iter_no_change': 20,  # Early stopping patience
                'random_state': 42
            }
        
        model = GradientBoostingRegressor(**params)
        model.fit(X_train, y_train)
        
        # Evaluate
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)
        
        scores = {
            'train_rmse': np.sqrt(mean_squared_error(y_train, train_pred)),
            'test_rmse': np.sqrt(mean_squared_error(y_test, test_pred)),
            'train_mae': mean_absolute_error(y_train, train_pred),
            'test_mae': mean_absolute_error(y_test, test_pred),
            'train_r2': r2_score(y_train, train_pred),
            'test_r2': r2_score(y_test, test_pred)
        }
        
        logger.info(f"Gradient Boosting - Test RMSE: {scores['test_rmse']:.6f}, R²: {scores['test_r2']:.4f}")
        
        return model, scores
    
    def train_all_models(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        models_to_train: List[str] = None
    ) -> Dict[str, Tuple]:
        """
        Train all specified models.
        
        Args:
            X_train: Training features
            y_train: Training target
            X_test: Test features
            y_test: Test target
            X_val: Validation features (optional, for early stopping)
            y_val: Validation target (optional, for early stopping)
            models_to_train: List of model names to train
        
        Returns:
            Dictionary of trained models and their scores
        """
        if models_to_train is None:
            models_to_train = ['xgboost', 'lightgbm', 'catboost', 'random_forest', 'gradient_boosting']
        
        results = {}
        
        for model_name in models_to_train:
            try:
                if model_name == 'xgboost':
                    model, scores = self.train_xgboost(X_train, y_train, X_test, y_test, X_val, y_val)
                elif model_name == 'lightgbm':
                    model, scores = self.train_lightgbm(X_train, y_train, X_test, y_test, X_val, y_val)
                elif model_name == 'catboost':
                    model, scores = self.train_catboost(X_train, y_train, X_test, y_test, X_val, y_val)
                elif model_name == 'random_forest':
                    # Tune RF if enabled
                    if self.hyperparameter_tuner and X_val is not None and y_val is not None:
                        logger.info("Tuning Random Forest hyperparameters...")
                        params = self.hyperparameter_tuner.tune_random_forest(X_train, y_train, X_val, y_val)
                        model, scores = self.train_random_forest(X_train, y_train, X_test, y_test, params=params)
                    else:
                        model, scores = self.train_random_forest(X_train, y_train, X_test, y_test)
                elif model_name == 'gradient_boosting':
                    model, scores = self.train_gradient_boosting(X_train, y_train, X_test, y_test, X_val, y_val)
                elif model_name == 'lstm':
                    model, scores = self.train_lstm(X_train, y_train, X_test, y_test, X_val, y_val)
                else:
                    logger.warning(f"Unknown model: {model_name}")
                    continue
                
                results[model_name] = (model, scores)
                self.models[model_name] = model
                self.model_scores[model_name] = scores
                
                # Save model
                if model_name == 'lstm':
                    model_path = self.models_dir / f"{model_name}.h5"
                    model.save(str(model_path))
                else:
                    model_path = self.models_dir / f"{model_name}.pkl"
                    joblib.dump(model, model_path)
                logger.info(f"Saved {model_name} to {model_path}")
                
            except Exception as e:
                logger.error(f"Error training {model_name}: {e}")
                continue
        
        return results
    
    def get_best_model(self, metric: str = 'test_r2') -> Tuple[str, object]:
        """
        Get the best performing model.
        
        Args:
            metric: Metric to use for comparison
        
        Returns:
            Tuple of (model_name, model)
        """
        if not self.model_scores:
            raise ValueError("No models trained yet")
        
        best_model_name = max(
            self.model_scores.keys(),
            key=lambda x: self.model_scores[x].get(metric, -float('inf'))
        )
        
        return best_model_name, self.models[best_model_name]
    
    def train_lstm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        params: Optional[Dict] = None
    ) -> Tuple:
        """Train LSTM model for time-series prediction."""
        try:
            from models.lstm_model import LSTMModel
        except ImportError:
            logger.warning("LSTM not available - TensorFlow not installed. Skipping LSTM training.")
            return None, {'test_rmse': float('inf'), 'test_r2': -float('inf')}
        
        if params is None:
            params = {
                'sequence_length': 60,
                'units': 128,
                'dropout': 0.2,
                'learning_rate': 0.001,
                'epochs': 100,
                'batch_size': 32
            }
        
        model = LSTMModel(
            sequence_length=params.get('sequence_length', 60),
            n_features=len(X_train.columns)
        )
        
        # Train model
        model.train(
            X_train, y_train,
            X_val, y_val,
            epochs=params.get('epochs', 100),
            batch_size=params.get('batch_size', 32),
            verbose=0
        )
        
        # Evaluate
        scores = model.evaluate(X_test, y_test)
        
        # Add train scores (approximate)
        train_pred = []
        for i in range(len(X_train)):
            try:
                pred = model.predict(X_train.iloc[i:i+1])
                train_pred.append(pred)
            except:
                train_pred.append(y_train.iloc[i])
        
        train_pred = np.array(train_pred)
        scores['train_rmse'] = np.sqrt(mean_squared_error(y_train, train_pred))
        scores['train_r2'] = r2_score(y_train, train_pred)
        
        return model, scores

