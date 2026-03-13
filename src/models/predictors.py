"""Prediction pipeline."""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from utils.logger import setup_logger
from models.model_selector import ModelSelector

logger = setup_logger(__name__)


class PricePredictor:
    """Main prediction class that orchestrates model predictions."""
    
    def __init__(
        self,
        model_selector: ModelSelector,
        prediction_horizon: str = "1h",
        confidence_threshold: float = 0.65,
        config: Optional[Dict] = None
    ):
        """
        Initialize price predictor.
        
        Args:
            model_selector: ModelSelector instance
            prediction_horizon: Time horizon for prediction (e.g., "1h", "4h")
            confidence_threshold: Minimum confidence to make predictions
            config: Optional configuration dictionary for accessing additional settings
        """
        self.model_selector = model_selector
        self.prediction_horizon = prediction_horizon
        self.confidence_threshold = confidence_threshold
        self.config = config or {}
    
    def predict(
        self,
        features: pd.DataFrame,
        current_price: float,
        method: str = 'ensemble'
    ) -> Dict:
        """
        Make price prediction.
        
        Args:
            features: Feature dataframe
            current_price: Current market price
            method: Prediction method ('ensemble', 'best_single')
        
        Returns:
            Dictionary with prediction results
        """
        try:
            # Get predictions
            if method == 'ensemble':
                prediction = self.model_selector.predict_ensemble(features, method='weighted_average')
                confidence = self.model_selector.get_model_confidence(features)
            else:
                model_name, prediction = self.model_selector.get_best_single_prediction(features)
                confidence = 0.7  # Default confidence for single model
            
            # Handle single prediction (scalar)
            if np.isscalar(prediction):
                prediction = np.array([prediction])
            
            # Get mean prediction
            predicted_return = float(np.mean(prediction))
            
            # Calculate predicted price
            predicted_price = current_price * (1 + predicted_return)
            
            # Determine direction
            direction = 'LONG' if predicted_return > 0 else 'SHORT'
            
            # Check confidence threshold
            is_confident = confidence >= self.confidence_threshold
            
            result = {
                'predicted_return': predicted_return,
                'predicted_price': predicted_price,
                'current_price': current_price,
                'price_change_pct': predicted_return * 100,
                'direction': direction,
                'confidence': confidence,
                'is_confident': is_confident,
                'prediction_horizon': self.prediction_horizon,
                'timestamp': datetime.now()
            }
            
            logger.info(
                f"Prediction: {direction} | "
                f"Return: {predicted_return*100:.2f}% | "
                f"Confidence: {confidence:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return {
                'predicted_return': 0.0,
                'predicted_price': current_price,
                'current_price': current_price,
                'price_change_pct': 0.0,
                'direction': 'HOLD',
                'confidence': 0.0,
                'is_confident': False,
                'error': str(e)
            }

