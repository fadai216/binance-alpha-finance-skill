# Alpha 4× Stability API

## 文档入口

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

## 1. 获取稳定性分析

- 方法：`GET`
- 路径：`/alpha/stability`

### Query 参数

- `top`
  - 类型：`integer`
  - 默认：`6`
  - 范围：`1-20`
  - 含义：返回前 N 个综合评分最低、相对更稳定的代币

### 响应字段

- `analysis`
  - 排序后的代币分析结果数组
- `alerts`
  - 提醒文案数组
- `recommendation`
  - 自然语言推荐文本
- `updated_at`
  - 本次分析更新时间，ISO 8601
- `source`
  - 数据来源模式
  - 可能值：
    - `page+alpha-api`
    - `alpha-api`
    - `alpha-api-fallback`
    - `cached-discovery`
- `window_minutes`
  - 分析窗口，默认 `60`
- `total_symbols`
  - 当前完整监控标的总数
- `last_refresh_error`
  - 最近一次刷新失败信息；若为空表示最近刷新成功
- `diagnostics`
  - 抓取诊断信息，便于前端或 Skill 判断当前是否用了页面回退或缓存回退
- `scheduler_state`
  - scheduler 连续失败次数、最近尝试时间、最近成功时间

### `analysis[]` 字段

- `symbol`
  - 前端展示符号，例如 `LABUSDT`
- `volatility`
  - 最近 1 小时波动率
- `spread`
  - 最近 1 小时平均相对价差
- `score`
  - 综合评分，公式：`volatility * 0.6 + spread * 0.4`
- `market_symbol`
  - Binance Alpha 内部交易对，例如 `ALPHA_804USDT`
- `chain_name`
  - 链名
- `error`
  - 单个代币分析失败时的错误文本

### 响应示例

```json
{
  "analysis": [
    {
      "symbol": "LABUSDT",
      "volatility": 0.0021,
      "spread": 0.0023,
      "score": 0.0022,
      "market_symbol": "ALPHA_123USDT",
      "chain_name": "BSC",
      "error": null
    },
    {
      "symbol": "GUAUSDT",
      "volatility": 0.003,
      "spread": 0.0029,
      "score": 0.00296,
      "market_symbol": "ALPHA_456USDT",
      "chain_name": "BSC",
      "error": null
    }
  ],
  "alerts": [
    "🔔 新上线 4×积分代币: XXX",
    "⚠️ 波动率过高代币: YYY"
  ],
  "recommendation": "Alpha 4×积分代币稳定性排名（最近1小时）...",
  "updated_at": "2026-03-14T05:32:59.000000+00:00",
  "source": "alpha-api-fallback",
  "window_minutes": 60,
  "total_symbols": 8,
  "last_refresh_error": null,
  "diagnostics": {
    "used_cached_discovery": false,
    "four_x_total": 8,
    "page_match_count": 0,
    "points_page": {
      "status": "waf_challenge",
      "status_code": 202,
      "waf_challenge": true
    }
  },
  "scheduler_state": {
    "consecutive_failures": 0,
    "last_attempt_at": "2026-03-14T05:32:59.000000+00:00",
    "last_success_at": "2026-03-14T05:32:59.000000+00:00",
    "last_error": null,
    "last_error_at": null
  }
}
```

## 2. 健康检查

## 2. 获取历史趋势快照

- 方法：`GET`
- 路径：`/alpha/stability/history`

### Query 参数

- `limit`
  - 类型：`integer`
  - 默认：`12`
  - 范围：`1-120`
  - 含义：返回最近 N 条历史快照

### 响应结构

```json
[
  {
    "timestamp": "2026-03-14T13:40:00+08:00",
    "analysis": [
      {
        "symbol": "LABUSDT",
        "volatility": 0.0021,
        "spread": 0.0023,
        "score": 0.0018
      },
      {
        "symbol": "GUAUSDT",
        "volatility": 0.003,
        "spread": 0.0029,
        "score": 0.0022
      }
    ],
    "alerts": [
      "⚠️ 波动率过高代币: LYNUSDT"
    ]
  }
]
```

### 用途

- 前端绘制多分钟趋势图
- 回看 volatility / spread / score 的历史变化
- 标注 alert 事件时间点

## 3. 健康检查

- 方法：`GET`
- 路径：`/health`

### 响应

```json
{
  "status": "ok"
}
```

## 告警规则

- 新代币上线：`🔔 新上线 4×积分代币: ...`
  - 使用“历史已见集合”做增量识别
  - 冷启动首轮不会把当前全量代币误报为新币
- 高波动提醒：`⚠️ 波动率过高代币: ...`
  - 触发条件：`volatility > 0.007`

## 降级语义

- 页面被 WAF challenge 时：
  - `source` 可能返回 `alpha-api-fallback`
  - `diagnostics.points_page.status = waf_challenge`
- 代币发现接口失败但本地有历史跟踪列表时：
  - `source = cached-discovery`
  - 仍会尝试基于已缓存交易对继续刷新 volatility / spread
- 当前刷新失败但本地有上次缓存时：
  - `/alpha/stability` 优先返回最近一次缓存结果
  - 同时在 `last_refresh_error` 中提供失败信息

## 4. 获取币安理财产品

- 方法：`GET`
- 路径：`/binance/finance`

### Query 参数

- `sort_by`
  - 可选：`apr | term_days | product_name`
- `order`
  - 可选：`asc | desc`
- `product_type`
  - 可选：`all | flexible | locked | activity`
- `limit`
  - 默认：`20`

## 5. 获取币安活动列表

- 方法：`GET`
- 路径：`/binance/finance/activity`

### Query 参数

- `status`
  - 可选：`all | active | expired | unknown`
- `reward_type`
  - 可选：`all | apr | points | voucher | token | unknown`
- `limit`
  - 默认：`20`

## 6. 获取理财与活动历史快照

- 方法：`GET`
- 路径：`/binance/finance/history`

### Query 参数

- `limit`
  - 默认：`12`
  - 含义：返回最近 N 条理财/活动快照，用于前端历史趋势图
