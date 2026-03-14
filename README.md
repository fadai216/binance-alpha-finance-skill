# binance-alpha-finance

OpenClaw skill for:

- Binance Alpha 4x points token stability analysis
- Binance finance product discovery
- Binance activity discovery
- finance history snapshots
- `product_id` based finance history queries

This repository is self-hosted by default:

- includes its own FastAPI backend under `backend/`
- includes helper scripts under `scripts/`
- can be cloned directly into `~/.openclaw/skills/binance-alpha-finance`

## Repository Layout

```text
binance-alpha-finance/
├── SKILL.md
├── config.json
├── apis.json
├── backend/
│   ├── alpha_monitor/
│   ├── finance_monitor/
│   ├── data/
│   ├── API.md
│   ├── main.py
│   ├── requirements.txt
│   └── scheduler.py
└── scripts/
    ├── ensure_backend.sh
    ├── install.sh
    ├── query.py
    ├── query.sh
    ├── start_api.sh
    └── start_scheduler.sh
```

## Install

### Option A: clone directly into OpenClaw skills

```bash
git clone <YOUR_GITHUB_REPO_URL> ~/.openclaw/skills/binance-alpha-finance
```

Then run:

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/ensure_backend.sh
```

### Option B: clone anywhere, then install

```bash
git clone <YOUR_GITHUB_REPO_URL>
cd binance-alpha-finance
bash scripts/install.sh
```

## First Run

Start backend if not already running:

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/ensure_backend.sh
```

This will:

1. create `backend/.venv/`
2. install Python dependencies
3. start `uvicorn` on `127.0.0.1:8000`

## Query Examples

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh alpha 'top=3'
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh finance 'sort_by=apr&order=desc&product_type=all&limit=5'
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh activity 'status=active&reward_type=all&limit=5'
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh finance-history 'product_id=activity:65317d61d1c445f99f73a04c05233dd2&limit=5'
```

## Config

Edit `config.json` if needed:

- `apiBaseUrl`
- `apiHost`
- `apiPort`
- `backendRoot`
- `venvDir`

Default is local self-hosting on:

- `http://127.0.0.1:8000`

## Optional Binance API Credentials

If you want the full official Simple Earn product pool instead of fallback/public-derived data, set:

```bash
export BINANCE_API_KEY="..."
export BINANCE_API_SECRET="..."
```

Then restart the backend.

## Notes

- If port `8000` is already occupied but `/health` responds normally, `ensure_backend.sh` treats the backend as healthy.
- Without Binance API credentials, the finance module falls back to Binance CMS/public activity data and derives finance products from announcements.
- Runtime files, caches, sqlite snapshots, and `.venv/` are excluded by `.gitignore`.

