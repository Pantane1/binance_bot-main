# Model Reloading & Context Preservation Guide

## ✅ Yes, You Can Retrain While Bot is Running!

The bot now supports **hot-reloading** of models, meaning you can retrain models while the bot is running and it will automatically pick them up.

## 🔄 How It Works

### 1. **Retrain While Bot is Running**

**Step 1**: Run your bot normally:
```bash
python main.py
```

**Step 2**: In another terminal, retrain models:
```bash
python retrain_models.py
```

**Step 3**: The bot automatically detects new models (within 5 minutes) and reloads them!

**What happens:**
- Bot checks for new models every 5 minutes
- If it detects recently updated model files, it reloads them
- Trading continues seamlessly with new models
- No restart needed!

### 2. **On Bot Restart**

**You will NOT lose context or accuracy!**

**What's preserved:**
- ✅ **Models**: Loaded from disk (`models/*.pkl` files)
- ✅ **Positions**: Synced from exchange automatically
- ✅ **Database**: All trades and positions persisted
- ✅ **Model performance**: Same models = same accuracy

**What happens on restart:**
1. Bot tries to load existing models from disk
2. If found → uses them immediately (no retraining needed)
3. If not found → trains new models
4. Positions synced from exchange
5. Trading continues with full context

## 📋 Detailed Behavior

### Model Loading Priority

1. **On Startup**:
   - First: Try to load models from disk
   - If found: Use them (fast startup)
   - If not: Train new models

2. **While Running**:
   - Automatic retraining: Every 24 hours (configurable)
   - Manual retraining: Run `retrain_models.py` anytime
   - Auto-reload: Bot checks every 5 minutes for new models

3. **After Manual Retraining**:
   - Models saved to disk
   - Bot detects within 5 minutes
   - Automatically reloads and uses new models

### Position Context

- **On Restart**: Positions synced from exchange
- **Database**: All historical trades preserved
- **No Loss**: Full trading history maintained

### Model Accuracy

- **Same Models = Same Accuracy**: If you reload the same models, accuracy is identical
- **Better Models = Better Accuracy**: Newly retrained models may improve accuracy
- **No Degradation**: Restarting doesn't make models worse

## 🎯 Usage Scenarios

### Scenario 1: Manual Retraining While Running

```bash
# Terminal 1: Bot running
python main.py

# Terminal 2: Retrain models
python retrain_models.py

# Bot automatically picks up new models within 5 minutes
```

### Scenario 2: Restart After Retraining

```bash
# Step 1: Retrain models
python retrain_models.py

# Step 2: Restart bot
python main.py

# Bot loads the newly trained models from disk
```

### Scenario 3: Restart Without Retraining

```bash
# Just restart
python main.py

# Bot loads existing models from disk (if they exist)
# Or trains new ones if no models found
```

## ⚙️ Configuration

### Model Reload Check Frequency

Currently checks every **5 minutes**. To change, modify in `main.py`:

```python
# Check every 2 minutes instead
schedule.every(120).seconds.do(reload_models_job)
```

### Automatic Retraining Frequency

In `config/config.yaml`:

```yaml
models:
  retrain_frequency: 86400  # 24 hours (in seconds)
```

Change to:
- `3600` = 1 hour
- `43200` = 12 hours
- `604800` = 7 days (weekly)

## 🔍 Monitoring

### Check if Models Were Reloaded

Look for these log messages:

```
INFO - Detected new models on disk, reloading...
INFO - Loaded xgboost from models/xgboost.pkl
INFO - Models reloaded successfully!
```

### Check Model Age

Models are saved with timestamps. Check file modification time:

```bash
# Windows
dir models\*.pkl

# Linux/Mac
ls -lh models/*.pkl
```

## ⚠️ Important Notes

### Model File Safety

- Models are saved to disk immediately after training
- Old models are overwritten (not backed up)
- Consider backing up models before retraining if needed

### Performance Impact

- **Reloading**: Very fast (< 1 second)
- **Retraining**: Takes 5-15 minutes (runs in background)
- **Trading**: Continues normally during retraining

### Best Practices

1. **Let automatic retraining handle it**: Set appropriate frequency
2. **Manual retraining**: Use when you want immediate updates
3. **Restart after major changes**: If you change config significantly
4. **Monitor logs**: Watch for reload messages

## 🎓 Summary

### Can I retrain while bot is running?
✅ **YES** - Run `retrain_models.py` in another terminal, bot auto-reloads within 5 minutes

### Will I lose context on restart?
❌ **NO** - Models loaded from disk, positions synced from exchange, database preserved

### Will I lose accuracy on restart?
❌ **NO** - Same models = same accuracy. Better models = better accuracy.

### What's the best workflow?
1. Let automatic retraining run (daily/weekly)
2. Manual retrain when needed (market changes, improvements)
3. Restart anytime - everything is preserved

---

**Your bot is now fully persistent and supports hot-reloading! 🚀**

