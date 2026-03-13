"""Test script to verify Trading AI setup."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_imports():
    """Test if all required packages are installed."""
    print("Testing imports...")
    try:
        import pandas
        import numpy
        import sklearn
        import xgboost
        import lightgbm
        import catboost
        import binance
        import ta
        print("✓ All core packages imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Please install missing packages: pip install -r requirements.txt")
        return False

def test_config():
    """Test if configuration file exists and is valid."""
    print("\nTesting configuration...")
    try:
        from utils.helpers import load_config
        config = load_config()
        print("✓ Configuration file loaded successfully")
        print(f"  - Trading mode: {config['trading']['mode']}")
        print(f"  - Symbols: {config['trading']['symbols']}")
        print(f"  - Testnet: {config['binance']['testnet']}")
        return True
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False

def test_binance_connection():
    """Test Binance API connection."""
    print("\nTesting Binance connection...")
    load_dotenv()
    
    api_key = os.getenv('BINANCE_API_KEY', '')
    api_secret = os.getenv('BINANCE_API_SECRET', '')
    
    if not api_key or not api_secret:
        print("⚠ Binance API credentials not found in .env file")
        print("  Set BINANCE_API_KEY and BINANCE_API_SECRET")
        return False
    
    try:
        from data_collection.binance_client import BinanceClient
        client = BinanceClient(api_key, api_secret, testnet=True)
        
        # Test connection
        ticker = client.get_ticker('BTCUSDT')
        if ticker:
            print("✓ Binance connection successful")
            print(f"  - BTCUSDT price: {ticker.get('lastPrice', 'N/A')}")
            return True
        else:
            print("✗ Could not fetch ticker data")
            return False
    except Exception as e:
        print(f"✗ Binance connection error: {e}")
        print("  Check your API credentials and internet connection")
        return False

def test_data_collection():
    """Test data collection."""
    print("\nTesting data collection...")
    try:
        from data_collection.binance_client import BinanceClient
        from dotenv import load_dotenv
        import os
        
        load_dotenv()
        api_key = os.getenv('BINANCE_API_KEY', '')
        api_secret = os.getenv('BINANCE_API_SECRET', '')
        
        if not api_key or not api_secret:
            print("⚠ Skipping - API credentials not available")
            return False
        
        client = BinanceClient(api_key, api_secret, testnet=True)
        df = client.get_klines('BTCUSDT', '1h', limit=100)
        
        if not df.empty:
            print(f"✓ Data collection successful")
            print(f"  - Collected {len(df)} candles")
            print(f"  - Date range: {df.index[0]} to {df.index[-1]}")
            return True
        else:
            print("✗ No data collected")
            return False
    except Exception as e:
        print(f"✗ Data collection error: {e}")
        return False

def test_feature_engineering():
    """Test feature engineering."""
    print("\nTesting feature engineering...")
    try:
        from feature_engineering.technical_indicators import TechnicalIndicators
        import pandas as pd
        import numpy as np
        
        # Create sample data
        dates = pd.date_range('2024-01-01', periods=100, freq='1H')
        sample_data = pd.DataFrame({
            'open': np.random.randn(100).cumsum() + 100,
            'high': np.random.randn(100).cumsum() + 101,
            'low': np.random.randn(100).cumsum() + 99,
            'close': np.random.randn(100).cumsum() + 100,
            'volume': np.random.rand(100) * 1000
        }, index=dates)
        
        indicators = TechnicalIndicators()
        df_with_features = indicators.add_all_indicators(sample_data)
        
        print(f"✓ Feature engineering successful")
        print(f"  - Original features: {len(sample_data.columns)}")
        print(f"  - Features after engineering: {len(df_with_features.columns)}")
        return True
    except Exception as e:
        print(f"✗ Feature engineering error: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 50)
    print("Trading AI Setup Test")
    print("=" * 50)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Binance Connection", test_binance_connection()))
    results.append(("Data Collection", test_data_collection()))
    results.append(("Feature Engineering", test_feature_engineering()))
    
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n🎉 All tests passed! System is ready to use.")
        print("\nNext steps:")
        print("1. Review config/config.yaml")
        print("2. Run: python main.py")
    else:
        print("\n⚠ Some tests failed. Please fix the issues above.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

