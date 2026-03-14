# Release v1.4.0

## Highlights

- Added Binance Web3 Wallet DeFi earn pools monitoring
- Added proxy-aware network configuration through `config.json`
- Added stronger retry and exponential backoff support
- Added automatic history pruning and manual prune script
- Added Alembic scaffolding for future DB migrations
- Added algorithm transparency documentation
- Added pytest smoke tests
- Added GitHub Actions CI workflow
- Added minimal `/dashboard` page for local debugging

## Major APIs

- `GET /alpha/stability`
- `GET /alpha/stability/ranked`
- `GET /alpha/stability/trends`
- `GET /binance/finance`
- `GET /binance/finance/activity`
- `GET /binance/finance/activity/scored`
- `GET /binance/finance/recommend`
- `GET /binance/finance/history`
- `GET /binance/copilot/summary`
- `GET /binance/web3/earn/pools`

## Tooling

- `scripts/ensure_backend.sh`
- `scripts/prune_data.sh`
- `scripts/migrate.sh`
- `scripts/generate_examples.py`
- `tests/`
- `.github/workflows/ci.yml`

