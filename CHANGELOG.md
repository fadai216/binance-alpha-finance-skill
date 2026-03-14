# Changelog

All notable changes to this repository will be documented in this file.

## v1.4.0

- Added `web3_wallet_monitor` module for Binance Web3 Wallet DeFi earn pools
- New endpoint: `GET /binance/web3/earn/pools`
  - Real-time Venus (BSC) + Aave (ETH) lending pool data
  - Composite scoring: APY, TVL safety, protocol trust, stablecoin bonus
  - Filters: protocol, network, token_type, min_apy
  - Top picks: best stablecoin APY, best volatile APY, largest TVL pool
  - Protocol summary with aggregate stats
- Health endpoint now reports web3 pool data freshness and count
- Scheduler auto-refreshes web3 pools alongside alpha and finance data
- LLM copilot switched to direct HTTP calls (proxy-compatible, no SDK)
- CORS origins now default to localhost-only for security
- SQLite WAL mode enabled for history stores
- In-memory TTL caching (20s) across all three data services
- Scheduler: graceful SIGTERM/SIGINT shutdown + exponential backoff

## v1.1.3

- Added `query.py` output modes:
  - `--pretty`
  - `--raw`
  - `--save`
- Added `examples/` directory with real JSON outputs
- Added `scripts/generate_examples.py`
- Improved repository documentation for CLI and examples

## v1.1.2

- Added short query aliases:
  - `ranked`
  - `trends`
  - `scored`
  - `recommend`
  - `summary`
- Added Chinese OpenClaw prompt examples

## v1.1.1

- Updated `SKILL.md` and `apis.json` with:
  - scored activity endpoint
  - finance recommendation endpoint
  - alpha trend endpoint
  - copilot summary endpoint

## v1.1.0

- Added structured activity participation scoring
- Added low-barrier activity filtering
- Added finance recommendation scoring
- Added alpha risk ranking and trend APIs
- Added copilot summary API

## v1.0.0

- Initial open-source release
- Self-hosted OpenClaw packaging
- Alpha stability APIs
- Finance, activity, and history APIs

