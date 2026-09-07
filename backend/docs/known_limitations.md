# Known Limitations

This document outlines the modeling limitations of the HFT backtesting framework. Users should be aware of these constraints when interpreting backtest results.

## 1. Queue-position overstatement (L2 data limitation)
The framework uses standard L2 (market by price) data rather than L3 (market by order). This means our queue position tracking is a statistical approximation. The simulator relies on cancellation models (pessimistic, proportional, or power-law) to estimate queue depletion. This inherently overstates queue position stability compared to the real market where large orders may cancel abruptly.

## 2. Simplified SPAN margin
The margin engine computes a simplified version of SPAN margin based on 16 scenario scans. It does not perfectly replicate the exchange's exact margin requirements, particularly around calendar spreads and complex cross-margin benefits. Treat margin values as directional approximations.

## 3. No intraday margin calls from exchange
The backtester does not simulate intraday margin calls or forced liquidations by the exchange. If equity drops below the maintenance margin requirement intraday, the framework assumes the trader handles it according to their logic. The `RiskManager` can halt trading upon a daily drawdown limit, but explicit margin calls are absent.

## 4. Corporate action coverage requires user-supplied data
Corporate actions (dividends, splits, bonuses, mergers) are supported by the `CorporateActions` engine, but the data must be supplied by the user. The framework does not fetch or infer corporate actions automatically from standard OHLCV or L2 datasets. Failing to provide this data will result in incorrect PnL and price band calculations.

## 5. Options pricing assumes Black-Scholes
The Greeks calculation engine natively uses the Black-Scholes-Merton model. This assumes constant volatility and risk-free rates, log-normal distribution of underlying prices, and European-style exercise. It does not account for early exercise premiums (irrelevant for NSE post-2021, but relevant for historical data) or volatility smiles/skews out-of-the-box unless custom volatility surfaces are fed.

## 6. European-style pricing only (pre-2021 transition caveat)
Since 2021, all NSE stock options are European style. However, if you are backtesting with data prior to this transition, be aware that the framework does not currently calculate American-style early exercise premiums. 

## 7. Stat-arb pair stability
For statistical arbitrage, the framework assumes pairs remain cointegrated out-of-sample. Users must strictly separate their pair discovery phase from the backtesting window to avoid data snooping. The framework enforces a `PairDiscoveryViolationError` if the API is misused, but cannot prevent look-ahead bias if the pair definitions are hardcoded based on future knowledge.
