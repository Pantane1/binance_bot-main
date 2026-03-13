## Trading AI – Rules of the Game

This document explains **what the bot actually does**, how **profit taking and risk control** work, and what happens on **disconnect/reconnect**.

---

## 1. What markets it trades

- **Exchange**: Binance (spot and/or USDT‑M futures, depending on `config.yaml`).
- **Environment**: Testnet or mainnet controlled by:
  - `binance.testnet: true/false`
  - `binance.futures_testnet: true/false`
- **Symbols**: The list in `trading.symbols` in `config.yaml` (e.g. `BTCUSDT`, `ETHUSDT`, `XRPUSDT`, etc.).

The bot loops over each symbol and runs a **trading cycle** every `data_collection.market_data.update_frequency` seconds (default 60s).

---

## 2. How entries (opening trades) work

### 2.1 Data & features

For each symbol the bot collects:

- Recent OHLCV candles (multiple intervals, e.g. `1m`, `5m`, `15m`, `1h`, `4h`, `1d`).
- Technical indicators (RSI, MACD, Bollinger Bands, ADX, ATR, OBV, etc.).
- Order book features (bid/ask volumes, spread, imbalance, etc.).
- Futures metrics (funding rate, open interest, long/short ratio).
- Sentiment features (Twitter/Reddit/News) when available, otherwise neutral defaults.
- Wallet/on‑chain proxy features (currently placeholder).

A **feature dataframe** is built, with a target `future_return` (e.g. 1h ahead price return).

### 2.2 Models and predictions

- Multiple ML models are trained (XGBoost, LightGBM, CatBoost, Random Forest, Gradient Boosting).
- An **ensemble** combines their predictions into a single `predicted_return` and a **confidence** score.
- The prediction is turned into a direction:
  - `LONG` if `predicted_return > 0`
  - `SHORT` if `predicted_return < 0`
  - `HOLD` if prediction sign is effectively zero.

The **confidence** is based on **agreement between models** (how similar their predictions are). Low disagreement → high confidence. The confidence threshold is configurable via `prediction.confidence_threshold` (default 0.65). Lower values allow more trades but lower quality signals.

### 2.3 Signal generation rules

For each symbol, the strategy (`TradingStrategy.generate_signal`) will:

1. Get a prediction and confidence from the ensemble.
2. **Check max positions per symbol**: If `max_positions_per_symbol` (default: 3) is reached for this symbol/direction, skip the signal.
3. **Reject** the trade if:
   - `prediction.is_confident` is `False` (confidence below `prediction.confidence_threshold` in `config.yaml`), or
   - Direction is `HOLD`.
4. Compute **stop loss (SL)** and **take profit (TP)** around current price:
   - From `trading.risk` in `config.yaml`:
     - `stop_loss_pct` (e.g. 0.015 = 1.5%)
     - `risk_reward_ratio` (e.g. 0.5 = 1:2 risk:reward, more generous)
     - `take_profit_pct` (e.g. 0.03 = 3%, can override R:R calculation)
   - For a LONG:
     - `SL = entry_price * (1 - stop_loss_pct)`
     - `TP = entry_price * (1 + take_profit_pct)` or `entry_price * (1 + stop_loss_pct / risk_reward_ratio)`
   - For a SHORT:
     - `SL = entry_price * (1 + stop_loss_pct)`
     - `TP = entry_price * (1 - take_profit_pct)` or `entry_price * (1 - stop_loss_pct / risk_reward_ratio)`
5. Choose **leverage**:
   - Spot: `leverage = 1`
   - Futures: `leverage = max_leverage` from `trading.risk.max_leverage` (e.g. 15x), subject to liquidation safety checks.
6. Validate the trade via `RiskManager.validate_trade`:
   - **Daily loss limit** not breached (`max_daily_loss`).
   - **Risk/Reward** ≤ configured `risk_reward_ratio` (you demand at least 1:2 reward relative to risk by default).
   - **Leverage** ≤ `max_leverage`.
   - **Liquidation buffer** respected for futures (distance to liquidation price ≥ `liquidation_buffer`, default 6%).
7. Compute **position size** via `RiskManager.calculate_position_size`:
   - Uses account equity, `risk_per_trade` (e.g. 1.5% of balance), and the distance between entry and SL.
   - Caps notional size by `max_position_size` (e.g. 5% of equity).
8. If everything passes, a **signal dictionary** is created and logged, including:
   - `symbol`, `direction`, `entry_price`, `stop_loss`, `take_profit`,
   - `position_size`, `leverage`, `predicted_return`, `confidence`, etc.

This signal is then handed to the `TradeExecutor` to actually place the order.

---

## 3. Order placement & precision

The `TradeExecutor` handles order execution:

1. **Side**: `BUY` for LONG, `SELL` for SHORT.
2. **Quantity**:
   - The raw `position_size` from the strategy is passed to `BinanceClient.quantize_quantity`.
   - `quantize_quantity` looks up the symbol’s **LOT_SIZE** step (e.g. 0.001 BTC) and **floors** the size to a valid multiple.
   - This avoids `APIError(code=-1111): quantity has too much precision`.
3. **Order types**:
   - Currently uses **MARKET** orders for both spot and futures.
   - SL/TP are tracked in the bot logic, not yet placed as separate stop/limit orders on the exchange.
4. On success:
   - An entry is stored in `active_positions` dict (in memory) with:
     - `symbol`, `direction`, `entry_price`, `stop_loss`, `take_profit`,
     - `position_size`, `leverage`, `futures` flag, and `entry_time`.

> Note: This in‑memory tracking is per **process run**. It does not yet persist positions or automatically reload them after a restart (see Section 5).

---

## 4. Profit taking & exits

The exit logic lives in `TradingStrategy.should_exit_position` and `TradeExecutor.close_position`.

### 4.1 Hard exit rules

For each open position and current price:

- **Stop loss (SL)**:
  - LONG: if `current_price <= stop_loss` → exit reason `"Stop loss hit"`.
  - SHORT: if `current_price >= stop_loss` → exit reason `"Stop loss hit"`.

- **Take profit (TP)**:
  - LONG: if `current_price >= take_profit` → exit reason `"Take profit hit"`.
  - SHORT: if `current_price <= take_profit` → exit reason `"Take profit hit"`.

These are defined at entry based on your configured `stop_loss_pct` and `risk_reward_ratio`.

### 4.2 Trailing stop (NEW)

When enabled (`trailing_stop.enabled: true`), the bot uses a **trailing stop** to protect profits:

- **Activation**: Trailing starts once price reaches `activate_rr` (default: 1.0 = 1R profit).
- **Behavior**:
  - For LONG: Tracks highest favorable price, moves SL up by `trail_pct` (default: 1%) behind peak.
  - For SHORT: Tracks lowest favorable price, moves SL down by `trail_pct` behind trough.
- **Protection**: Stop loss never moves against you (only locks in profits).
- **Exit**: If price hits trailing stop → exit reason `"Trailing stop loss hit"`.

### 4.3 Partial profit taking (NEW)

The bot can take profits in **chunks** for disciplined gain collection:

- **Configuration**: `partial_take_profits` in `config.yaml` defines profit levels:
  ```yaml
  partial_take_profits:
    - { fraction: 0.5, rr_multiple: 1.0 }   # Sell 50% at 1R
    - { fraction: 0.5, rr_multiple: 2.0 }   # Sell remaining 50% at 2R
  ```
- **Execution**:
  - When price hits 1R profit → closes 50% of position (reason: `"PARTIAL_TP_1.0R_0.5"`).
  - When price hits 2R profit → closes remaining 50% (reason: `"PARTIAL_TP_2.0R_0.5"`).
  - Position continues with reduced `remaining_size` until fully closed.
- **Benefits**: Locks in profits early while letting winners run.

### 4.4 Model‑driven exit

Even if SL/TP are not hit, the bot can exit early when the **model view reverses**:

- For the current bar:
  - Get a fresh prediction and direction (`LONG`, `SHORT`, `HOLD`).
  - If the **new predicted direction is opposite** the open position's direction, and
  - The prediction **confidence > 0.7**, then:
    - Exit with reason `"Prediction reversed with high confidence"`.

This acts like a dynamic stop‑and‑reverse rule, but only when the model is very sure.

### 4.5 Liquidation‑risk exit (futures)

For futures positions with leverage > 1:

- The bot estimates **liquidation price** and the distance from current price.
- If the distance falls below your configured `liquidation_buffer` (default: 6%):
  - Exit with reason `"Liquidation risk too high"`.

### 4.6 Executing the exit

- When an exit condition is met, the bot calls `TradeExecutor.close_position`:
  - **Partial exits**: Closes only the specified fraction, updates `remaining_size`.
  - **Full exits**: Places a **MARKET** order in the opposite direction with the stored `position_size` or `remaining_size`.
  - Removes position from `active_positions` (full exit) or updates it (partial exit).
  - **Database persistence**: All exits are logged to database (if configured) with realized PnL.
  - Logs the close and reason.

Currently, there are **no on‑exchange stop/limit orders** being placed; all SL/TP logic is managed by the bot and executed via market orders when conditions are met.

---

## 5. Disconnect & reconnect behaviour

### 5.1 What happens on disconnect

If the bot process is stopped (crash, restart, manual stop):

- In‑memory `active_positions` are **lost**.
- Any positions already open on Binance (spot or futures) **remain open** on the exchange.
- The exchange still enforces its own liquidation and margin rules; the bot just isn’t managing exits while down.

### 5.2 On reconnect (current behaviour)

When you restart `main.py`:

- **Position syncing**: The bot calls `TradeExecutor.update_positions()` at the start of each trading cycle.
- **Futures positions**: For futures trading, the bot:
  - Fetches all open positions from Binance via `futures_position_information()`.
  - Rebuilds `active_positions` dict with current exchange positions.
  - Recalculates stop loss and take profit for each position using current risk parameters.
  - **Database persistence**: If database is configured, positions are stored and can be queried.
- **Spot positions**: Spot positions are tracked in-memory and via database, but exchange sync is limited (Binance spot API doesn't provide easy position tracking).

The bot will **automatically detect and manage positions** that were opened before restart, ensuring continuity across sessions.

### 5.3 Database persistence (NEW)

The system now supports **persistent storage** of positions and trades:

- **Database options**: SQLite (default) or PostgreSQL (configurable).
- **Stored data**:
  - All positions (open and closed) with entry/exit prices, PnL, timestamps.
  - All trades (fills) with prices, quantities, fees, order IDs.
  - Position status tracking (OPEN/CLOSED).
- **Benefits**:
  - Positions survive bot restarts.
  - Historical trade analysis via Jupyter notebooks.
  - Performance tracking and accounting.
  - Audit trail of all trading activity.

Configuration in `config.yaml`:
```yaml
database:
  type: "sqlite"  # or "postgres"
  path: "data/trading_data.db"  # for SQLite
  # url: "postgresql+psycopg2://..."  # for PostgreSQL
```

---

## 6. Risk management summary

Risk is governed by `trading.risk` in `config.yaml`:

- **Per‑trade risk**: `risk_per_trade` (default: 0.015 = 1.5% of equity at SL).
- **Max position notional**: `max_position_size` (default: 0.05 = 5% of equity).
- **Max positions per symbol**: `max_positions_per_symbol` (default: 3) - allows pyramiding.
- **Stop loss**: `stop_loss_pct` (default: 0.015 = 1.5% from entry).
- **Take profit**: `take_profit_pct` (default: 0.03 = 3%) or derived via `risk_reward_ratio`.
- **Risk/Reward constraint**: `risk_reward_ratio` (default: 0.5 = 1:2, more generous than before).
- **Daily loss cap**: `max_daily_loss` (default: 0.05 = 5% of equity). Once hit, no further trades are allowed that day.
- **Leverage**: `max_leverage` for futures (default: 15x), with liquidation buffer checks.
- **Liquidation buffer**: `liquidation_buffer` (default: 0.06 = 6% minimum distance from liquidation price).
- **Partial profit taking**: `partial_take_profits` - takes profits in chunks at specified R multiples.
- **Trailing stop**: `trailing_stop` - protects winners by moving stop loss behind peak price.

The `RiskManager` enforces these limits **before** any order is sent and logs a reason when a potential trade is rejected.

---\n\n## 7. Summary of “rules of the game”\n\n- The bot **only trades when**:\n  - The ensemble model predicts a clear direction with confidence ≥ your threshold.\n  - The proposed trade passes all risk checks (per‑trade risk, R:R ratio, leverage, liquidation buffer, daily loss limit).\n- **Entries**: Market orders sized by risk (1% of equity risk, max 5% notional) with SL/TP set to enforce your R:R profile.\n- **Exits**:\n  - Hard SL/TP based on price levels.\n  - Early exit on strong model reversal.\n  - Early exit on dangerous liquidation proximity (futures).\n- **Reconnect**: Current session‑only position tracking. Open positions from previous sessions are not yet auto‑managed after restart.\n- **Precision & compliance**: Quantizes all quantities to Binance’s lot size rules to avoid precision errors.\n- **Safety**: Validates API keys/permissions/IP on startup and fails fast if anything is wrong.\n\nThis document reflects the current implemented behaviour; any strategy or risk parameter changes should be mirrored here to keep the “rules of the game” in sync with the code.\n*** End Patch***"}}} atsopano to=functions.apply_patch никто ***!

