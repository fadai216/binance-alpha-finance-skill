# Binance Alpha Finance Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](./backend/requirements.txt)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688.svg)](./backend/main.py)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Skill-black.svg)](./SKILL.md)

Self-hosted OpenClaw skill for:

- Binance Alpha 4x points token stability analysis
- Binance finance product discovery
- Binance activity discovery
- product-level finance history
- scored activities and low-barrier filtering
- finance recommendations
- Alpha risk ranking and trend analysis
- Binance copilot daily summary

中文文档：

- [docs/TUTORIAL.zh-CN.md](./docs/TUTORIAL.zh-CN.md)
- [docs/OPENCLAW_PROMPTS.zh-CN.md](./docs/OPENCLAW_PROMPTS.zh-CN.md)
- [docs/ALGORITHM.md](./docs/ALGORITHM.md)

## Features

### Alpha

- `GET /alpha/stability`
- `GET /alpha/stability/history`
- `GET /alpha/stability/ranked`
- `GET /alpha/stability/trends`

Alpha outputs include:

- `volatility`
- `spread`
- `score`
- `risk_score`
- `risk_label`
- `abnormal_flag`
- `risk_reason`

### Finance

- `GET /binance/finance`
- `GET /binance/finance/activity`
- `GET /binance/finance/activity/scored`
- `GET /binance/finance/recommend`
- `GET /binance/finance/history`

Finance outputs include:

- `product_id`
- `source`
- `recommendation_score`
- `recommendation_reason`
- `risk_hint`
- `redeemable`

Activity outputs include:

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

### Copilot

- `GET /binance/copilot/summary`

Summary supports:

- `style=conservative`
- `style=balanced`
- `style=aggressive`

## Reliability & Operations

- Built-in retry and exponential backoff for Binance requests
- Proxy-aware startup through `config.json`
- Automatic periodic history pruning in scheduler
- Manual pruning:
  - `bash scripts/prune_data.sh`
- Minimal Alembic scaffolding for future migrations
- Minimal local debug dashboard:
  - `http://127.0.0.1:8000/dashboard`

## Repository Layout

```text
binance-alpha-finance-skill/
├── SKILL.md
├── README.md
├── CHANGELOG.md
├── LICENSE
├── config.json
├── apis.json
├── alembic.ini
├── .github/workflows/ci.yml
├── docs/
│   ├── ALGORITHM.md
│   ├── OPENCLAW_PROMPTS.zh-CN.md
│   ├── TUTORIAL.zh-CN.md
│   └── RELEASE_NOTES_*.md
├── examples/
│   ├── alpha-ranked.json
│   ├── alpha-trends.json
│   ├── finance-recommend.json
│   ├── activity-scored.json
│   └── copilot-summary.json
├── backend/
│   ├── alpha_monitor/
│   ├── finance_monitor/
│   ├── web3_wallet_monitor/
│   ├── alembic/
│   ├── static/
│   ├── data/
│   ├── API.md
│   ├── http_utils.py
│   ├── prune_data.py
│   ├── main.py
│   ├── scheduler.py
│   ├── requirements.txt
│   └── requirements-dev.txt
├── scripts/
│   ├── ensure_backend.sh
│   ├── start_api.sh
│   ├── start_scheduler.sh
│   ├── prune_data.sh
│   ├── migrate.sh
│   ├── query.py
│   ├── query.sh
│   ├── generate_examples.py
│   └── install.sh
└── tests/
    ├── conftest.py
    └── test_api_smoke.py
```

## Install

### Option A: clone directly into OpenClaw skills

```bash
git clone https://github.com/fadai216/binance-alpha-finance-skill.git ~/.openclaw/skills/binance-alpha-finance
bash ~/.openclaw/skills/binance-alpha-finance/scripts/ensure_backend.sh
```

### Option B: clone anywhere, then install

```bash
git clone https://github.com/fadai216/binance-alpha-finance-skill.git
cd binance-alpha-finance-skill
bash scripts/install.sh
```

## Config

Edit `config.json` if needed:

- `apiBaseUrl`
- `apiHost`
- `apiPort`
- `proxy`
- `noProxy`
- `backendRoot`
- `venvDir`
- `historyRetentionDays`
- `autoPruneIntervalHours`

Default local API:

- `http://127.0.0.1:8000`

Optional Binance credentials:

```bash
export BINANCE_API_KEY="..."
export BINANCE_API_SECRET="..."
```

## Common Commands

### Alpha

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh alpha "top=3"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh alpha-history "limit=12"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh ranked "top=3"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh trends "limit=6"
```

### Finance

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh finance "sort_by=apr&order=desc&product_type=all&limit=5"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh finance "sort_by=stability&order=desc&redeemable_only=true&limit=5"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh activity "status=active&reward_type=all&limit=5"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh activity "status=active&reward_type=all&low_barrier_only=true&max_capital=500&limit=5"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh scored "limit=3"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh recommend "sort_by=stability&limit=3"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh finance-history "product_id=activity:65317d61d1c445f99f73a04c05233dd2&limit=5"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh summary "style=balanced"
```

### Output Modes

```bash
python scripts/query.py summary "style=balanced" --pretty
python scripts/query.py summary "style=balanced" --raw
python scripts/query.py summary "style=balanced" --save
python scripts/query.py summary "style=balanced" --save ./summary.json
```

### Maintenance

```bash
bash scripts/prune_data.sh
bash scripts/migrate.sh
python scripts/generate_examples.py
```

## Testing

```bash
cd backend
python -m compileall .
cd ..
python -m pytest -q
```

GitHub Actions CI:

- `.github/workflows/ci.yml`

## Examples

Real sample outputs live in:

- [examples/](./examples/)

Regenerate them:

```bash
python scripts/generate_examples.py
```

## Notes

- If port `8000` is occupied but `/health` works, `ensure_backend.sh` treats the backend as healthy.
- This repository is backend-only and designed primarily for skill usage.
- Runtime files, sqlite snapshots, caches, and `.venv/` are ignored by `.gitignore`.
- For API details, see [backend/API.md](./backend/API.md).

