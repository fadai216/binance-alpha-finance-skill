# Release v1.1.0

## Highlights

- Added structured activity participation scoring
- Added low-barrier activity filtering support
- Added finance recommendation scoring
- Added Alpha risk ranking fields
- Added Alpha risk trend API
- Added Binance Copilot summary API

## New Endpoints

- `GET /binance/finance/activity/scored`
- `GET /binance/finance/recommend`
- `GET /alpha/stability/ranked`
- `GET /alpha/stability/trends`
- `GET /binance/copilot/summary`

## New Activity Fields

- `score`
- `score_label`
- `reasons`
- `participation_difficulty`
- `time_urgency`
- `complexity_score`
- `requires_kyc`
- `requires_holding`
- `requires_region_eligibility`
- `requires_trading_volume`
- `restriction_flags`
- `low_barrier`
- `low_barrier_reason`

## New Finance Fields

- `recommendation_score`
- `recommendation_reason`
- `risk_hint`
- `redeemable`

## New Alpha Fields

- `risk_score`
- `risk_label`
- `abnormal_flag`
- `risk_reason`
- trend delta fields in `/alpha/stability/trends`

