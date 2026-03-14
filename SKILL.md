---
name: binance-alpha-finance
description: |
  本地 Binance Alpha + Finance 聚合 skill。用于查询 Alpha 4×积分代币稳定性、币安理财产品、
  活动列表、历史快照，以及按 product_id 查询理财产品历史。支持活动评分、理财推荐、Alpha 风险趋势、
  今日机会总结。优先调用本机 FastAPI 后端。
argument-hint: [alpha / ranked / trends / finance / activity / scored / recommend / summary / product_id]
allowed-tools: Bash(curl *), Bash(python *), Bash(uvicorn *), Bash(bash *)
---

# Binance Alpha Finance Skill

## Use This Skill When

- 用户要查 Binance Alpha 4×积分代币稳定性
- 用户要查币安理财产品、APR、期限、奖励、活动
- 用户要按 `product_id` 查理财产品历史快照
- 用户要查活动是否值得参加
- 用户要筛选低门槛活动
- 用户要查理财推荐结果
- 用户要查 Alpha 风险排序或风险趋势
- 用户要查今日 Binance 机会总结
- 用户要确认后端接口、scheduler、SQLite 历史是否正常

## Local Service

默认调用 skill 自带后端：

- API Base: `http://127.0.0.1:8000`
- Backend Root: `./backend`

如果服务未启动，可先运行：

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/start_scheduler.sh
bash ~/.openclaw/skills/binance-alpha-finance/scripts/start_api.sh
```

或自动检查并拉起：

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/ensure_backend.sh
```

## Core Endpoints

### Alpha

- `GET /alpha/stability?top=6`
- `GET /alpha/stability/history?limit=12`
- `GET /alpha/stability/ranked?top=6`
- `GET /alpha/stability/trends?limit=12`

### Finance

- `GET /binance/finance`
  - 参数：
    - `sort_by=apr|term|term_days|product_name|stability|recommendation`
    - `order=asc|desc`
    - `product_type=all|flexible|locked|activity`
    - `min_apr=<n>`
    - `max_term=<days>`
    - `redeemable_only=true|false`
    - `source=<signed-sapi|activity-derived|public-finance-fallback>`
    - `limit=<n>`
- `GET /binance/finance/activity`
  - 参数：
    - `status=all|active|expired|unknown`
    - `reward_type=all|apr|points|voucher|token|unknown`
    - `max_capital=<usd>`
    - `low_barrier_only=true|false`
    - `active_only=true|false`
    - `limit=<n>`
- `GET /binance/finance/activity/scored`
  - 参数：
    - `status=all|active|expired|unknown`
    - `reward_type=all|apr|points|voucher|token|unknown`
    - `max_capital=<usd>`
    - `low_barrier_only=true|false`
    - `active_only=true|false`
    - `limit=<n>`
- `GET /binance/finance/recommend`
  - 参数：
    - `min_apr=<n>`
    - `max_term=<days>`
    - `redeemable_only=true|false`
    - `source=<signed-sapi|activity-derived|public-finance-fallback>`
    - `product_type=all|flexible|locked|activity`
    - `sort_by=apr|term|term_days|stability|recommendation`
    - `order=asc|desc`
    - `limit=<n>`
- `GET /binance/finance/history`
  - 参数：
    - `limit=<n>`
    - `product_id=<stable_id>` 优先
    - `symbol=<name_or_asset>` 兼容回退

### Copilot Summary

- `GET /binance/copilot/summary`
  - 参数：
    - `style=conservative|balanced|aggressive`

## Important Output Fields

### Finance Product

- `product_id`
- `product_name`
- `product_type`
- `asset`
- `apr`
- `term_days`
- `min_purchase_amount`
- `available_balance`
- `reward_label`
- `reward_type`
- `source`
- `recommendation_score`
- `recommendation_reason`
- `risk_hint`
- `redeemable`

### Finance Product Source

- `signed-sapi`
  - 官方 Simple Earn signed API
- `activity-derived`
  - 从活动公告中派生出的理财产品
- `public-finance-fallback`
  - 公开回退链路或旧快照补全来源

### Scored Activity Fields

- `score`
- `score_label`
- `reasons`
- `participation_difficulty`
- `time_urgency`
- `complexity_score`
- `estimated_min_requirement`
- `estimated_min_requirement_usd`
- `low_barrier`
- `low_barrier_reason`
- `requires_kyc`
- `requires_holding`
- `requires_region_eligibility`
- `requires_trading_volume`
- `restriction_flags`

### Alpha Risk Fields

- `risk_score`
- `risk_label`
- `abnormal_flag`
- `risk_reason`
- `trend_label`
- `trend_reason`
- `risk_delta`

## Recommended Query Order

1. 先跑 `ensure_backend.sh`
2. Alpha 查询走 `/alpha/stability`
3. 理财产品走 `/binance/finance`
4. 需要可参与度时走 `/binance/finance/activity/scored`
5. 需要理财推荐时走 `/binance/finance/recommend`
6. 单产品历史优先带 `product_id`
7. 总结类问题走 `/binance/copilot/summary`

## Examples

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh alpha "top=3"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh alpha-history "limit=12"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh ranked "top=3"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh trends "limit=6"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh finance "sort_by=apr&order=desc&product_type=all&limit=5"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh finance "sort_by=stability&order=desc&redeemable_only=true&limit=5"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh activity "status=active&reward_type=all&limit=5"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh activity "status=active&reward_type=all&low_barrier_only=true&max_capital=500&limit=5"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh finance-history "product_id=activity:65317d61d1c445f99f73a04c05233dd2&limit=5"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh scored "limit=3"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh recommend "sort_by=stability&limit=3"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh summary "style=balanced"
```

## Portability

别人可以直接从 GitHub 下载这个 skill 后本地使用，前提是：

1. 把整个 `binance-alpha-finance/` 目录放到：
   - `~/.openclaw/skills/binance-alpha-finance`
2. 首次执行：
   - `bash ~/.openclaw/skills/binance-alpha-finance/scripts/ensure_backend.sh`
3. 本机能访问 `http://127.0.0.1:8000`
4. 如果想拿完整官方 Simple Earn 产品池，需要配置：
   - `BINANCE_API_KEY`
   - `BINANCE_API_SECRET`

如果不想本地自托管，也可以把 `config.json` 的 `apiBaseUrl` 改成别人自己的公网 API。
