# Model Performance Improvements

## Overview

This document describes the improvements made to address low R² scores and improve model performance.

## Implemented Improvements

### 1. Feature Selection (`src/models/feature_selector.py`)

**Problem**: Too many features can lead to overfitting and poor generalization. Many features may be redundant or irrelevant.

**Solution**: Implemented multiple feature selection methods:

- **Mutual Information**: Selects features with highest mutual information with target
- **Correlation**: Selects features most correlated with target
- **Feature Importance**: Uses Random Forest to rank features by importance
- **Combined Method**: Weighted combination of all three methods (recommended)

**Benefits**:
- Reduces overfitting
- Improves model generalization
- Faster training
- Better interpretability

**Usage**: Automatically enabled in `ModelTrainer` when `use_feature_selection=True` (default).

### 2. Hyperparameter Tuning (`src/models/hyperparameter_tuner.py`)

**Problem**: Default hyperparameters are often suboptimal for specific datasets.

**Solution**: Implemented Optuna-based hyperparameter tuning:

- **TPE Sampler**: Tree-structured Parzen Estimator for efficient search
- **Median Pruner**: Early stopping of unpromising trials
- **Model-specific tuning**: Optimized parameter spaces for each model type

**Supported Models**:
- XGBoost
- LightGBM
- CatBoost
- Random Forest

**Benefits**:
- Better model performance
- Optimized for your specific data
- Automatic parameter optimization

**Usage**: Automatically enabled when `hyperparameter_tuning.enabled=true` in config (default).

### 3. LSTM Model (`src/models/lstm_model.py`)

**Problem**: Traditional ML models don't capture temporal dependencies well in time-series data.

**Solution**: Implemented LSTM (Long Short-Term Memory) neural network:

- **Sequence-based learning**: Uses 60 time steps of historical data
- **Deep architecture**: 3-layer LSTM with batch normalization and dropout
- **Early stopping**: Prevents overfitting
- **Learning rate scheduling**: Adaptive learning rate reduction

**Benefits**:
- Captures temporal patterns
- Better for time-series forecasting
- Can learn complex non-linear relationships

**Requirements**: 
- TensorFlow (optional, install with `pip install tensorflow`)
- More training time and computational resources

**Usage**: Include `"lstm"` in `models_to_train` list in config.

### 4. Enhanced Model Training Pipeline

**Improvements**:
- Automatic removal of highly correlated features (>0.95 correlation)
- Feature selection integrated into training pipeline
- Hyperparameter tuning before model training
- Better handling of validation sets for early stopping

## Configuration

Update `config/config.yaml` to control these features:

```yaml
models:
  # Feature Selection
  use_feature_selection: true
  feature_selection_method: "combined"  # Options: "mutual_info", "correlation", "importance", "combined"
  
  # Hyperparameter Tuning
  hyperparameter_tuning:
    enabled: true
    method: "optuna"
    n_trials: 100  # More trials = better results but slower
  
  # Models to train
  models_to_train:
    - "xgboost"
    - "lightgbm"
    - "catboost"
    - "random_forest"
    - "gradient_boosting"
    - "lstm"  # Requires TensorFlow
```

## Expected Improvements

### Before (Current State):
- R²: 0.02-0.03 (very low)
- Models barely better than random
- Low confidence scores (0.53-0.56)

### After (With Improvements):
- **R²: 0.10-0.25** (5-10x improvement expected)
- Better feature selection reduces noise
- Optimized hyperparameters improve fit
- LSTM captures temporal patterns
- Higher confidence scores (0.60-0.75 expected)

## Installation

Install new dependencies:

```bash
pip install optuna
```

For LSTM support (optional):

```bash
pip install tensorflow
```

## Usage

### Automatic (Recommended)

The improvements are automatically applied when training models:

```bash
python retrain_models.py --lookback 5000
```

### Manual Training

The `ModelTrainer` now automatically:
1. Removes constant features
2. Removes highly correlated features
3. Applies feature selection (if enabled)
4. Tunes hyperparameters (if enabled)
5. Trains all models including LSTM (if enabled)

## Performance Notes

### Training Time
- **Without tuning**: ~5-10 minutes per model
- **With tuning (100 trials)**: ~30-60 minutes per model
- **LSTM**: Additional 10-20 minutes

### Recommendations
1. **Start with feature selection ON, tuning OFF** for faster iteration
2. **Enable tuning** when you have time for better results
3. **Add LSTM** if you have TensorFlow and want to capture temporal patterns
4. **Use more data**: `--lookback 5000` or more for better results

## Troubleshooting

### LSTM Not Training
- Install TensorFlow: `pip install tensorflow`
- Check that you have enough data (need at least `sequence_length` samples)

### Hyperparameter Tuning Too Slow
- Reduce `n_trials` in config (e.g., 50 instead of 100)
- Disable tuning for faster training: `enabled: false`

### Feature Selection Issues
- If too few features selected, adjust `n_features` in `FeatureSelector`
- Try different selection methods

## Next Steps

1. **Retrain models** with new improvements:
   ```bash
   python retrain_models.py --lookback 5000
   ```

2. **Monitor results**:
   - Check R² scores (should be higher)
   - Check confidence scores (should be higher)
   - Monitor trading performance

3. **Iterate**:
   - Adjust feature selection method if needed
   - Tune hyperparameter trial count
   - Add/remove models as needed

## Technical Details

### Feature Selection Algorithm
1. Calculate mutual information scores
2. Calculate correlation scores
3. Calculate Random Forest importance scores
4. Normalize and combine (40% MI, 30% correlation, 30% importance)
5. Select top N features (auto: 60% of features, min 20)

### Hyperparameter Tuning
- Uses Optuna's TPE sampler for efficient search
- Median pruner stops unpromising trials early
- Optimizes for validation RMSE
- Saves best parameters for model training

### LSTM Architecture
- Input: 60 time steps × N features
- Layer 1: 128 LSTM units (return sequences)
- Layer 2: 64 LSTM units (return sequences)
- Layer 3: 32 LSTM units
- Dense layers: 64 → 32 → 1 (output)
- Dropout: 0.2 between layers
- Batch normalization for stability

