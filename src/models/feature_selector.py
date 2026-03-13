"""Feature selection for improving model performance."""

import pandas as pd
import numpy as np
from sklearn.feature_selection import (
    mutual_info_regression,
    SelectKBest,
    f_regression,
    RFE,
    SelectFromModel
)
from sklearn.ensemble import RandomForestRegressor
from typing import List, Tuple, Optional, Dict
from utils.logger import setup_logger

logger = setup_logger(__name__)


class FeatureSelector:
    """Advanced feature selection for time-series trading data."""
    
    def __init__(self, method: str = 'combined'):
        """
        Initialize feature selector.
        
        Args:
            method: Selection method ('mutual_info', 'correlation', 'importance', 'combined')
        """
        self.method = method
        self.selected_features = None
        self.feature_scores = {}
    
    def select_features(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_features: Optional[int] = None,
        method: Optional[str] = None
    ) -> Tuple[pd.DataFrame, List[str], Dict[str, float]]:
        """
        Select best features using specified method.
        
        Args:
            X: Feature dataframe
            y: Target variable
            n_features: Number of features to select (None = auto)
            method: Override default method
        
        Returns:
            Selected features dataframe, feature names, feature scores
        """
        method = method or self.method
        
        if n_features is None:
            # Auto-select: use 50-80% of features, minimum 20
            n_features = max(20, int(len(X.columns) * 0.6))
        
        logger.info(f"Selecting {n_features} features from {len(X.columns)} using method: {method}")
        
        if method == 'mutual_info':
            return self._select_mutual_info(X, y, n_features)
        elif method == 'correlation':
            return self._select_correlation(X, y, n_features)
        elif method == 'importance':
            return self._select_importance(X, y, n_features)
        elif method == 'combined':
            return self._select_combined(X, y, n_features)
        else:
            logger.warning(f"Unknown method {method}, using all features")
            return X, list(X.columns), {}
    
    def _select_mutual_info(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_features: int
    ) -> Tuple[pd.DataFrame, List[str], Dict[str, float]]:
        """Select features using mutual information."""
        # Calculate mutual information scores
        mi_scores = mutual_info_regression(X.fillna(0), y, random_state=42)
        
        # Create feature scores dictionary
        feature_scores = dict(zip(X.columns, mi_scores))
        
        # Select top N features
        top_indices = np.argsort(mi_scores)[-n_features:][::-1]
        selected_features = [X.columns[i] for i in top_indices]
        
        logger.info(f"Selected {len(selected_features)} features using mutual information")
        logger.debug(f"Top 10 MI scores: {sorted(feature_scores.items(), key=lambda x: x[1], reverse=True)[:10]}")
        
        return X[selected_features], selected_features, feature_scores
    
    def _select_correlation(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_features: int
    ) -> Tuple[pd.DataFrame, List[str], Dict[str, float]]:
        """Select features using correlation with target."""
        # Calculate correlation with target
        correlations = X.fillna(0).corrwith(y).abs()
        
        # Create feature scores dictionary
        feature_scores = correlations.to_dict()
        
        # Select top N features
        top_features = correlations.nlargest(n_features).index.tolist()
        
        logger.info(f"Selected {len(top_features)} features using correlation")
        logger.debug(f"Top 10 correlations: {correlations.nlargest(10).to_dict()}")
        
        return X[top_features], top_features, feature_scores
    
    def _select_importance(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_features: int
    ) -> Tuple[pd.DataFrame, List[str], Dict[str, float]]:
        """Select features using Random Forest importance."""
        # Train a quick RF to get feature importance
        rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        rf.fit(X.fillna(0), y)
        
        # Get feature importances
        importances = pd.Series(rf.feature_importances_, index=X.columns)
        
        # Create feature scores dictionary
        feature_scores = importances.to_dict()
        
        # Select top N features
        top_features = importances.nlargest(n_features).index.tolist()
        
        logger.info(f"Selected {len(top_features)} features using RF importance")
        logger.debug(f"Top 10 importances: {importances.nlargest(10).to_dict()}")
        
        return X[top_features], top_features, feature_scores
    
    def _select_combined(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_features: int
    ) -> Tuple[pd.DataFrame, List[str], Dict[str, float]]:
        """Combine multiple selection methods for robust feature selection."""
        # Get scores from all methods
        mi_scores = mutual_info_regression(X.fillna(0), y, random_state=42)
        mi_scores_norm = (mi_scores - mi_scores.min()) / (mi_scores.max() - mi_scores.min() + 1e-8)
        
        corr_scores = X.fillna(0).corrwith(y).abs()
        corr_scores_norm = (corr_scores - corr_scores.min()) / (corr_scores.max() - corr_scores.min() + 1e-8)
        
        # Quick RF for importance
        rf = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
        rf.fit(X.fillna(0), y)
        imp_scores = pd.Series(rf.feature_importances_, index=X.columns)
        imp_scores_norm = (imp_scores - imp_scores.min()) / (imp_scores.max() - imp_scores.min() + 1e-8)
        
        # Combine scores (weighted average)
        combined_scores = (
            0.4 * pd.Series(mi_scores_norm, index=X.columns) +
            0.3 * corr_scores_norm +
            0.3 * imp_scores_norm
        )
        
        # Create feature scores dictionary
        feature_scores = combined_scores.to_dict()
        
        # Select top N features
        top_features = combined_scores.nlargest(n_features).index.tolist()
        
        logger.info(f"Selected {len(top_features)} features using combined method")
        logger.debug(f"Top 10 combined scores: {combined_scores.nlargest(10).to_dict()}")
        
        return X[top_features], top_features, feature_scores
    
    def remove_correlated_features(
        self,
        X: pd.DataFrame,
        threshold: float = 0.95
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Remove highly correlated features to reduce redundancy.
        
        Args:
            X: Feature dataframe
            threshold: Correlation threshold (features above this are removed)
        
        Returns:
            Filtered dataframe and remaining feature names
        """
        corr_matrix = X.fillna(0).corr().abs()
        
        # Find pairs of highly correlated features
        upper_triangle = corr_matrix.where(
            np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
        )
        
        # Find features to drop
        to_drop = [column for column in upper_triangle.columns if any(upper_triangle[column] > threshold)]
        
        if to_drop:
            logger.info(f"Removing {len(to_drop)} highly correlated features (threshold: {threshold})")
            X_filtered = X.drop(columns=to_drop)
            return X_filtered, list(X_filtered.columns)
        
        return X, list(X.columns)

