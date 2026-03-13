"""Model selection and ensemble methods."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ModelSelector:
    """Select and combine models for predictions."""
    
    def __init__(self, models: Dict, model_scores: Dict, feature_names: Optional[List[str]] = None):
        """
        Initialize model selector.
        
        Args:
            models: Dictionary of trained models
            model_scores: Dictionary of model performance scores
            feature_names: List of feature names used during training (for alignment)
        """
        self.models = models
        self.model_scores = model_scores
        self.feature_names = feature_names
        self.weights = self._calculate_weights()
    
    def _calculate_weights(self, method: str = 'performance') -> Dict[str, float]:
        """
        Calculate ensemble weights for models.
        
        Args:
            method: Weight calculation method ('performance', 'equal', 'inverse_rmse')
        
        Returns:
            Dictionary of model weights
        """
        if method == 'equal':
            n_models = len(self.models)
            return {name: 1.0 / n_models for name in self.models.keys()}
        
        elif method == 'performance':
            # Weight by R² score
            weights = {}
            total_score = 0
            
            for name, scores in self.model_scores.items():
                # Use test R², ensure positive
                score = max(scores.get('test_r2', 0), 0.01)
                weights[name] = score
                total_score += score
            
            # Normalize
            if total_score > 0:
                weights = {k: v / total_score for k, v in weights.items()}
            else:
                # Fallback to equal weights
                n_models = len(self.models)
                weights = {name: 1.0 / n_models for name in self.models.keys()}
            
            return weights
        
        elif method == 'inverse_rmse':
            # Weight inversely by RMSE
            weights = {}
            inverse_scores = {}
            
            for name, scores in self.model_scores.items():
                rmse = scores.get('test_rmse', float('inf'))
                if rmse > 0:
                    inverse_scores[name] = 1.0 / rmse
                else:
                    inverse_scores[name] = 0.01
            
            total = sum(inverse_scores.values())
            if total > 0:
                weights = {k: v / total for k, v in inverse_scores.items()}
            else:
                n_models = len(self.models)
                weights = {name: 1.0 / n_models for name in self.models.keys()}
            
            return weights
        
        else:
            raise ValueError(f"Unknown weight method: {method}")
    
    def _align_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Align prediction features to match training features.
        
        Args:
            X: Feature dataframe for prediction
        
        Returns:
            Aligned feature dataframe with proper feature names
        """
        if self.feature_names is None:
            # Try to get feature names from first model
            try:
                first_model = list(self.models.values())[0]
                if hasattr(first_model, 'feature_names_in_'):
                    self.feature_names = list(first_model.feature_names_in_)
                elif hasattr(first_model, 'get_booster'):
                    # XGBoost
                    booster = first_model.get_booster()
                    self.feature_names = booster.feature_names
                elif hasattr(first_model, 'feature_name_'):
                    # LightGBM
                    self.feature_names = first_model.feature_name_
                else:
                    logger.warning("Could not determine feature names, using provided features as-is")
                    return X
            except Exception as e:
                logger.warning(f"Could not extract feature names: {e}, using provided features as-is")
                return X
        
        # Convert to DataFrame if it's a Series (single row prediction)
        if isinstance(X, pd.Series):
            X = X.to_frame().T
        
        # Ensure X is a DataFrame with columns
        if not isinstance(X, pd.DataFrame):
            raise ValueError(f"Expected DataFrame, got {type(X)}")
        
        # Create aligned dataframe with proper structure
        # Build aligned data as a list of lists to preserve order and structure
        aligned_data = []
        
        # For each row in X (usually just one row for prediction)
        for idx in X.index:
            row_data = []
            # Add all training features in the correct order
            for feature_name in self.feature_names:
                if feature_name in X.columns:
                    row_data.append(X.loc[idx, feature_name])
                else:
                    # Missing feature - fill with zero
                    row_data.append(0.0)
                    logger.debug(f"Missing feature '{feature_name}' in prediction data, filling with 0")
            aligned_data.append(row_data)
        
        # Create DataFrame with proper column names and index, ensuring exact feature order
        aligned_X = pd.DataFrame(
            aligned_data,
            index=X.index,
            columns=self.feature_names  # Explicitly set column names in training order
        )
        
        # Ensure column order matches exactly (should already match, but double-check)
        aligned_X = aligned_X[self.feature_names]
        
        # Verify column names match training feature names exactly
        if list(aligned_X.columns) != self.feature_names:
            logger.warning(
                f"Column order mismatch: expected {len(self.feature_names)} features, "
                f"got {len(aligned_X.columns)}. Reordering..."
            )
            aligned_X = aligned_X[self.feature_names]
        
        # Ensure DataFrame has proper dtypes (float64 for numeric features)
        for col in aligned_X.columns:
            if aligned_X[col].dtype not in [np.float64, np.float32, np.int64, np.int32]:
                aligned_X[col] = aligned_X[col].astype(np.float64)
        
        return aligned_X
    
    def predict_ensemble(
        self,
        X: pd.DataFrame,
        method: str = 'weighted_average'
    ) -> np.ndarray:
        """
        Make ensemble prediction.
        
        Args:
            X: Feature dataframe
            method: Ensemble method ('weighted_average', 'median', 'mean')
        
        Returns:
            Ensemble predictions
        """
        # Align features to match training
        X_aligned = self._align_features(X)
        
        predictions = {}
        
        for name, model in self.models.items():
            try:
                # LSTM uses different prediction interface
                if name == 'lstm' and hasattr(model, 'predict'):
                    # LSTM expects DataFrame and returns single value
                    pred = model.predict(X_aligned)
                    # Ensure it's an array
                    if isinstance(pred, (int, float)):
                        pred = np.array([pred])
                    elif isinstance(pred, np.ndarray) and pred.ndim == 0:
                        pred = np.array([pred.item()])
                    predictions[name] = pred
                else:
                    pred = model.predict(X_aligned)
                    predictions[name] = pred
            except Exception as e:
                logger.error(f"Error predicting with {name}: {e}")
                continue
        
        if not predictions:
            raise ValueError("No successful predictions")
        
        # Normalize all predictions to 1D arrays with same length
        normalized_predictions = []
        for name, pred in predictions.items():
            # Convert to numpy array if not already
            if not isinstance(pred, np.ndarray):
                pred = np.array(pred)
            
            # Flatten to 1D and ensure it's a single value
            pred = pred.flatten()
            if len(pred) == 0:
                continue
            # Take first value if multiple (shouldn't happen for single prediction)
            normalized_predictions.append(pred[0] if len(pred) > 0 else pred.item() if pred.ndim == 0 else pred)
        
        # Create array from normalized predictions
        pred_array = np.array(normalized_predictions)
        
        if method == 'weighted_average':
            weights_array = np.array([self.weights.get(name, 0) for name in predictions.keys()])
            if weights_array.sum() > 0:
                weights_array = weights_array / weights_array.sum()  # Normalize
            else:
                # Fallback to equal weights
                weights_array = np.ones(len(predictions)) / len(predictions)
            ensemble_pred = np.average(pred_array, weights=weights_array)
        
        elif method == 'median':
            ensemble_pred = np.median(pred_array)
        
        elif method == 'mean':
            ensemble_pred = np.mean(pred_array)
        
        else:
            raise ValueError(f"Unknown ensemble method: {method}")
        
        # Return as array for consistency
        return np.array([ensemble_pred])
    
    def get_best_single_prediction(self, X: pd.DataFrame) -> Tuple[str, np.ndarray]:
        """
        Get prediction from best single model.
        
        Args:
            X: Feature dataframe
        
        Returns:
            Tuple of (model_name, predictions)
        """
        # Align features to match training
        X_aligned = self._align_features(X)
        
        # Find best model by R²
        best_name = max(
            self.model_scores.keys(),
            key=lambda x: self.model_scores[x].get('test_r2', -float('inf'))
        )
        
        best_model = self.models[best_name]
        
        # Handle LSTM differently
        if best_name == 'lstm' and hasattr(best_model, 'predict'):
            predictions = best_model.predict(X_aligned)
            if isinstance(predictions, (int, float)):
                predictions = np.array([predictions])
            elif isinstance(predictions, np.ndarray) and predictions.ndim == 0:
                predictions = np.array([predictions.item()])
        else:
            predictions = best_model.predict(X_aligned)
        
        return best_name, predictions
    
    def get_model_confidence(self, X: pd.DataFrame) -> float:
        """
        Calculate confidence based on prediction agreement.
        
        Args:
            X: Feature dataframe
        
        Returns:
            Confidence score (0-1)
        """
        # Align features to match training
        X_aligned = self._align_features(X)
        
        predictions = {}
        
        for name, model in self.models.items():
            try:
                # LSTM uses different prediction interface
                if name == 'lstm' and hasattr(model, 'predict'):
                    pred = model.predict(X_aligned)
                    if isinstance(pred, (int, float)):
                        pred = np.array([pred])
                    elif isinstance(pred, np.ndarray) and pred.ndim == 0:
                        pred = np.array([pred.item()])
                    predictions[name] = pred
                else:
                    pred = model.predict(X_aligned)
                    predictions[name] = pred
            except Exception as e:
                logger.error(f"Error predicting with {name}: {e}")
                continue
        
        if len(predictions) < 2:
            return 0.5  # Default confidence
        
        # Normalize all predictions to 1D arrays with same length
        normalized_predictions = []
        for name, pred in predictions.items():
            # Convert to numpy array if not already
            if not isinstance(pred, np.ndarray):
                pred = np.array(pred)
            
            # Flatten to 1D and ensure it's a single value
            pred = pred.flatten()
            if len(pred) == 0:
                continue
            # Take first value if multiple (shouldn't happen for single prediction)
            normalized_predictions.append(pred[0] if len(pred) > 0 else pred.item() if pred.ndim == 0 else pred)
        
        # Create array from normalized predictions
        pred_array = np.array(normalized_predictions)
        
        # Calculate coefficient of variation (lower = more agreement = higher confidence)
        std = np.std(pred_array, axis=0)
        mean = np.abs(np.mean(pred_array, axis=0))
        mean = np.where(mean == 0, 1e-10, mean)  # Avoid division by zero
        cv = std / mean
        
        # Convert to confidence (inverse of CV, normalized)
        confidence = 1.0 / (1.0 + cv)
        return float(np.mean(confidence))

