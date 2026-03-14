# Release v1.2.0

## Highlights

- Added proxy-aware backend startup and request handling
- Added stronger request retry behavior with exponential backoff
- Added automatic history pruning support
- Added manual prune script
- Added Alembic scaffolding for future database migrations
- Added algorithm transparency documentation
- Added pytest smoke tests
- Added GitHub Actions CI workflow
- Added minimal local dashboard at `/dashboard`

## New Files

- `backend/http_utils.py`
- `backend/prune_data.py`
- `backend/requirements-dev.txt`
- `backend/static/dashboard.html`
- `scripts/prune_data.sh`
- `scripts/migrate.sh`
- `docs/ALGORITHM.md`
- `tests/`
- `.github/workflows/ci.yml`

## Notes

- Existing API compatibility is preserved.
- Scheduler logic remains compatible, with added periodic pruning.
- Proxy is configured through `config.json`.

