"""Enhanced hyperparameter tuning using Optuna."""

import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner
import numpy as np
from sklearn.metrics import mean_squared_error, r2_score
from typing import Dict, Optional, Callable, Tuple
import xgboost as xgb
import lightgbm as lgb
import catboost as cb
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from utils.logger import setup_logger

logger = setup_logger(__name__)


class HyperparameterTuner:
    """Advanced hyperparameter tuning with Optuna."""
    
    def __init__(self, n_trials: int = 100, timeout: Optional[int] = None):
        """
        Initialize hyperparameter tuner.
        
        Args:
            n_trials: Number of optimization trials
            timeout: Maximum time in seconds for optimization
        """
        self.n_trials = n_trials
        self.timeout = timeout
        self.best_params = {}
    
    def tune_xgboost(
        self,
        X_train,
        y_train,
        X_val,
        y_val,
        n_trials: Optional[int] = None
    ) -> Dict:
        """Tune XGBoost hyperparameters."""
        n_trials = n_trials or self.n_trials
        
        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 500, 3000),
                'max_depth': trial.suggest_int('max_depth', 4, 12),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'gamma': trial.suggest_float('gamma', 0.0, 0.5),
                'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 1.0),
                'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 2.0),
                'random_state': 42
            }
            
            model = xgb.XGBRegressor(**params)
            
            # Try to use early stopping
            try:
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    early_stopping_rounds=50,
                    verbose=False
                )
            except TypeError:
                # Fallback for newer XGBoost versions
                try:
                    params['early_stopping_rounds'] = 50
                    model = xgb.XGBRegressor(**params)
                    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
                except:
                    model.fit(X_train, y_train)
            
            val_pred = model.predict(X_val)
            rmse = np.sqrt(mean_squared_error(y_val, val_pred))
            return rmse
        
        study = optuna.create_study(
            direction='minimize',
            sampler=TPESampler(seed=42),
            pruner=MedianPruner(n_startup_trials=5)
        )
        
        study.optimize(objective, n_trials=n_trials, timeout=self.timeout, show_progress_bar=False)
        
        logger.info(f"XGBoost best params: {study.best_params}, best RMSE: {study.best_value:.6f}")
        return study.best_params
    
    def tune_lightgbm(
        self,
        X_train,
        y_train,
        X_val,
        y_val,
        n_trials: Optional[int] = None
    ) -> Dict:
        """Tune LightGBM hyperparameters."""
        n_trials = n_trials or self.n_trials
        
        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 500, 3000),
                'max_depth': trial.suggest_int('max_depth', 4, 12),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'num_leaves': trial.suggest_int('num_leaves', 31, 255),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'min_child_samples': trial.suggest_int('min_child_samples', 5, 50),
                'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 1.0),
                'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 1.0),
                'random_state': 42,
                'verbose': -1
            }
            
            model = lgb.LGBMRegressor(**params)
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
            )
            
            val_pred = model.predict(X_val)
            rmse = np.sqrt(mean_squared_error(y_val, val_pred))
            return rmse
        
        study = optuna.create_study(
            direction='minimize',
            sampler=TPESampler(seed=42),
            pruner=MedianPruner(n_startup_trials=5)
        )
        
        study.optimize(objective, n_trials=n_trials, timeout=self.timeout, show_progress_bar=False)
        
        logger.info(f"LightGBM best params: {study.best_params}, best RMSE: {study.best_value:.6f}")
        return study.best_params
    
    def tune_catboost(
        self,
        X_train,
        y_train,
        X_val,
        y_val,
        n_trials: Optional[int] = None
    ) -> Dict:
        """Tune CatBoost hyperparameters."""
        n_trials = n_trials or self.n_trials
        
        def objective(trial):
            params = {
                'iterations': trial.suggest_int('iterations', 500, 3000),
                'depth': trial.suggest_int('depth', 4, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1.0, 10.0),
                'random_seed': 42,
                'verbose': False
            }
            
            model = cb.CatBoostRegressor(**params)
            model.fit(
                X_train, y_train,
                eval_set=(X_val, y_val),
                early_stopping_rounds=50,
                verbose=False
            )
            
            val_pred = model.predict(X_val)
            rmse = np.sqrt(mean_squared_error(y_val, val_pred))
            return rmse
        
        study = optuna.create_study(
            direction='minimize',
            sampler=TPESampler(seed=42),
            pruner=MedianPruner(n_startup_trials=5)
        )
        
        study.optimize(objective, n_trials=n_trials, timeout=self.timeout, show_progress_bar=False)
        
        logger.info(f"CatBoost best params: {study.best_params}, best RMSE: {study.best_value:.6f}")
        return study.best_params
    
    def tune_random_forest(
        self,
        X_train,
        y_train,
        X_val,
        y_val,
        n_trials: Optional[int] = None
    ) -> Dict:
        """Tune Random Forest hyperparameters."""
        n_trials = n_trials or self.n_trials
        
        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 100, 500),
                'max_depth': trial.suggest_int('max_depth', 5, 20),
                'min_samples_split': trial.suggest_int('min_samples_split', 2, 20),
                'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 10),
                'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2', None]),
                'random_state': 42,
                'n_jobs': -1
            }
            
            model = RandomForestRegressor(**params)
            model.fit(X_train, y_train)
            
            val_pred = model.predict(X_val)
            rmse = np.sqrt(mean_squared_error(y_val, val_pred))
            return rmse
        
        study = optuna.create_study(
            direction='minimize',
            sampler=TPESampler(seed=42)
        )
        
        study.optimize(objective, n_trials=n_trials, timeout=self.timeout, show_progress_bar=False)
        
        logger.info(f"Random Forest best params: {study.best_params}, best RMSE: {study.best_value:.6f}")
        return study.best_params

