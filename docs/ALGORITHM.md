# Algorithm Notes

This document explains the current scoring and recommendation logic at a high level.

## 1. Alpha Stability

### Core score

For each Alpha token:

```text
score = volatility * 0.6 + spread * 0.4
```

- `volatility`
  - computed from 1-minute close prices in the last 60 minutes
  - uses the standard deviation of log returns
- `spread`
  - computed from relative bid/ask spread
  - averaged over recent snapshots

### Risk score

`risk_score` is derived from:

- volatility component
- spread component
- composite score component

Current rough weighting:

- volatility influence: about 45%
- spread influence: about 30%
- composite score influence: about 20%

Additional abnormal flags are raised when:

- volatility is above configured threshold
- spread is unusually wide
- total risk score is high

## 2. Finance Recommendation

Each finance product gets `recommendation_score` from:

- APR level
- redeemability / flexibility
- term length
- source reliability
- minimum requirement
- inferred risk hint

Approximate dimensions:

- APR attractiveness: high weight
- redeemability / term: medium-high weight
- source reliability: medium weight
- minimum capital requirement: medium weight
- risk hint adjustment: medium weight

## 3. Activity Participation Score

Each activity gets `score` from:

- reward strength
- time urgency
- participation difficulty
- restriction penalties
- active/expired state

Additional structured outputs:

- `participation_difficulty`
- `time_urgency`
- `complexity_score`
- `requires_kyc`
- `requires_holding`
- `requires_region_eligibility`
- `requires_trading_volume`
- `low_barrier`

## 4. Copilot Summary

`/binance/copilot/summary` aggregates:

- top Alpha opportunity
- top finance opportunity
- top scored activity
- Alpha risk trend summary

Styles:

- `conservative`
  - prefers lower risk and lower barrier
- `balanced`
  - mixes reward and risk
- `aggressive`
  - prefers higher upside candidates

## Important

These scores are heuristic.

They are designed for:

- ranking
- prioritization
- skill recommendations

They are not guarantees of profit, safety, or eligibility.

