"""LSTM model for time-series price prediction."""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import joblib
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger(__name__)

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.losses import MeanSquaredError
    from tensorflow.keras.metrics import MeanAbsoluteError
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logger.warning("TensorFlow not available. LSTM model will not work. Install with: pip install tensorflow")


class LSTMModel:
    """LSTM model for time-series forecasting."""
    
    def __init__(self, sequence_length: int = 60, n_features: int = None):
        """
        Initialize LSTM model.
        
        Args:
            sequence_length: Number of time steps to look back
            n_features: Number of input features
        """
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required for LSTM model. Install with: pip install tensorflow")
        
        self.sequence_length = sequence_length
        self.n_features = n_features
        self.model = None
        self.scaler_X = MinMaxScaler()
        self.scaler_y = MinMaxScaler()
        self.feature_names = None
    
    def _create_sequences(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sequence_length: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create sequences for LSTM input.
        
        Args:
            X: Feature array
            y: Target array
            sequence_length: Length of sequences
        
        Returns:
            X_sequences, y_sequences
        """
        X_sequences = []
        y_sequences = []
        
        for i in range(sequence_length, len(X)):
            X_sequences.append(X[i - sequence_length:i])
            y_sequences.append(y[i])
        
        return np.array(X_sequences), np.array(y_sequences)
    
    def build_model(
        self,
        input_shape: Tuple[int, int],
        units: int = 128,
        dropout: float = 0.2,
        learning_rate: float = 0.001
    ):
        """
        Build LSTM model architecture.
        
        Args:
            input_shape: (sequence_length, n_features)
            units: Number of LSTM units
            dropout: Dropout rate
            learning_rate: Learning rate
        """
        model = Sequential([
            LSTM(units, return_sequences=True, input_shape=input_shape),
            BatchNormalization(),
            Dropout(dropout),
            
            LSTM(units // 2, return_sequences=True),
            BatchNormalization(),
            Dropout(dropout),
            
            LSTM(units // 4, return_sequences=False),
            BatchNormalization(),
            Dropout(dropout),
            
            Dense(64, activation='relu'),
            Dropout(dropout),
            Dense(32, activation='relu'),
            Dense(1)
        ])
        
        optimizer = Adam(learning_rate=learning_rate)
        model.compile(optimizer=optimizer, loss='mse', metrics=['mae'])
        
        self.model = model
        logger.info(f"Built LSTM model with input shape {input_shape}")
    
    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        epochs: int = 100,
        batch_size: int = 32,
        verbose: int = 0
    ) -> Dict:
        """
        Train LSTM model.
        
        Args:
            X_train: Training features
            y_train: Training target
            X_val: Validation features
            y_val: Validation target
            epochs: Number of training epochs
            batch_size: Batch size
            verbose: Verbosity level
        
        Returns:
            Training history and scores
        """
        # Store feature names
        self.feature_names = list(X_train.columns)
        self.n_features = len(self.feature_names)
        
        # Scale features
        X_train_scaled = self.scaler_X.fit_transform(X_train)
        y_train_scaled = self.scaler_y.fit_transform(y_train.values.reshape(-1, 1)).flatten()
        
        # Create sequences
        X_train_seq, y_train_seq = self._create_sequences(
            X_train_scaled, y_train_scaled, self.sequence_length
        )
        
        # Build model if not already built
        if self.model is None:
            input_shape = (self.sequence_length, self.n_features)
            self.build_model(input_shape)
        
        # Prepare validation data
        validation_data = None
        if X_val is not None and y_val is not None and len(X_val) > self.sequence_length:
            X_val_scaled = self.scaler_X.transform(X_val)
            y_val_scaled = self.scaler_y.transform(y_val.values.reshape(-1, 1)).flatten()
            X_val_seq, y_val_seq = self._create_sequences(
                X_val_scaled, y_val_scaled, self.sequence_length
            )
            validation_data = (X_val_seq, y_val_seq)
        
        # Callbacks
        callbacks = [
            EarlyStopping(
                monitor='val_loss' if validation_data else 'loss',
                patience=20,
                restore_best_weights=True,
                verbose=verbose
            ),
            ReduceLROnPlateau(
                monitor='val_loss' if validation_data else 'loss',
                factor=0.5,
                patience=10,
                min_lr=1e-7,
                verbose=verbose
            )
        ]
        
        # Train model
        history = self.model.fit(
            X_train_seq, y_train_seq,
            validation_data=validation_data,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callbacks,
            verbose=verbose
        )
        
        logger.info(f"LSTM training completed. Final loss: {history.history['loss'][-1]:.6f}")
        
        return history
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make predictions.
        
        Args:
            X: Feature dataframe
        
        Returns:
            Predictions
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        # Ensure feature alignment
        if self.feature_names:
            missing_features = set(self.feature_names) - set(X.columns)
            if missing_features:
                logger.warning(f"Missing features: {missing_features}, filling with zeros")
                for feat in missing_features:
                    X[feat] = 0.0
            X = X[self.feature_names]
        
        # Scale features
        X_scaled = self.scaler_X.transform(X)
        
        # Create sequences (use last sequence_length points for prediction)
        if len(X_scaled) < self.sequence_length:
            # Pad with first value if not enough data
            padding = np.tile(X_scaled[0:1], (self.sequence_length - len(X_scaled), 1))
            X_scaled = np.vstack([padding, X_scaled])
        
        # Get last sequence
        X_seq = X_scaled[-self.sequence_length:].reshape(1, self.sequence_length, -1)
        
        # Predict
        y_pred_scaled = self.model.predict(X_seq, verbose=0)
        
        # Inverse transform
        y_pred = self.scaler_y.inverse_transform(y_pred_scaled.reshape(-1, 1)).flatten()
        
        return y_pred[0] if len(y_pred) == 1 else y_pred
    
    def evaluate(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> Dict:
        """
        Evaluate model on test set.
        
        Args:
            X_test: Test features
            y_test: Test target
        
        Returns:
            Evaluation metrics
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        # For evaluation, we need to create sequences
        X_test_scaled = self.scaler_X.transform(X_test)
        y_test_scaled = self.scaler_y.transform(y_test.values.reshape(-1, 1)).flatten()
        
        if len(X_test_scaled) < self.sequence_length:
            logger.warning("Test set too small for LSTM evaluation")
            return {'test_rmse': float('inf'), 'test_mae': float('inf'), 'test_r2': -float('inf')}
        
        X_test_seq, y_test_seq = self._create_sequences(
            X_test_scaled, y_test_scaled, self.sequence_length
        )
        
        # Predict
        y_pred_scaled = self.model.predict(X_test_seq, verbose=0)
        y_pred = self.scaler_y.inverse_transform(y_pred_scaled.reshape(-1, 1)).flatten()
        y_test_actual = self.scaler_y.inverse_transform(y_test_seq.reshape(-1, 1)).flatten()
        
        # Calculate metrics
        rmse = np.sqrt(mean_squared_error(y_test_actual, y_pred))
        mae = mean_absolute_error(y_test_actual, y_pred)
        r2 = r2_score(y_test_actual, y_pred)
        
        scores = {
            'test_rmse': rmse,
            'test_mae': mae,
            'test_r2': r2
        }
        
        logger.info(f"LSTM - Test RMSE: {rmse:.6f}, R²: {r2:.4f}")
        
        return scores
    
    def save(self, filepath: str):
        """Save model and scalers."""
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Save Keras model
        self.model.save(str(filepath))
        
        # Save scalers and metadata
        metadata = {
            'scaler_X': self.scaler_X,
            'scaler_y': self.scaler_y,
            'sequence_length': self.sequence_length,
            'n_features': self.n_features,
            'feature_names': self.feature_names
        }
        
        joblib.dump(metadata, str(filepath).replace('.h5', '_metadata.pkl'))
        logger.info(f"Saved LSTM model to {filepath}")
    
    @classmethod
    def load(cls, filepath: str):
        """Load model and scalers."""
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required for LSTM model")
        
        filepath = Path(filepath)
        metadata_path = str(filepath).replace('.h5', '_metadata.pkl')
        
        # Load metadata
        metadata = joblib.load(metadata_path)
        
        # Create instance
        instance = cls(
            sequence_length=metadata['sequence_length'],
            n_features=metadata['n_features']
        )
        
        # Load Keras model with compile=False to avoid metric deserialization issues
        try:
            # Try loading with compile=False first (avoids metric compatibility issues)
            instance.model = tf.keras.models.load_model(str(filepath), compile=False)
            # Recompile with simple metrics if needed (for training, but not required for inference)
            try:
                instance.model.compile(
                    optimizer=Adam(learning_rate=0.001),
                    loss=MeanSquaredError(),
                    metrics=[MeanAbsoluteError()]
                )
            except:
                # If compilation fails, that's okay - we only need it for prediction
                pass
        except Exception as e:
            # Fallback: try loading with custom objects
            try:
                custom_objects = {
                    'mse': tf.keras.losses.MeanSquaredError(),
                    'mae': tf.keras.metrics.MeanAbsoluteError()
                }
                instance.model = tf.keras.models.load_model(
                    str(filepath),
                    custom_objects=custom_objects,
                    compile=False
                )
            except Exception as e2:
                logger.error(f"Failed to load LSTM model: {e2}")
                raise
        
        instance.scaler_X = metadata['scaler_X']
        instance.scaler_y = metadata['scaler_y']
        instance.feature_names = metadata['feature_names']
        
        logger.info(f"Loaded LSTM model from {filepath}")
        return instance

