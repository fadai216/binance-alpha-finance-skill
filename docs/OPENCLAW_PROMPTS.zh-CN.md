# OpenClaw 直接调用示例

下面这些句子适合直接发给 OpenClaw。

## 启动

- 启动 `binance-alpha-finance` skill 后端
- 如果后端没启动，先安装依赖并启动

## Alpha

- 查 alpha 稳定性前 3 名
- 查 alpha 历史快照 12 条
- 查 alpha 风险排序前 5 名
- 查 alpha 风险趋势，最近 6 条快照

## Finance

- 查当前理财产品，按 APR 从高到低排序
- 查当前理财产品，按稳定性排序，只看可赎回产品
- 查 finance history，按 product_id 查询最近 5 条

## Activity

- 查当前活动列表
- 查值得参加的活动评分前 5 条
- 查低门槛活动，资金门槛不超过 500 美元
- 查 reward_type=apr 的活动

## Copilot Summary

- 总结今天 Binance 上最值得参与的机会
- 生成 balanced 风格的 Binance 机会总结
- 生成 conservative 风格的 Binance 机会总结
- 生成 aggressive 风格的 Binance 机会总结

## 对应命令示例

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh ranked "top=3"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh trends "limit=6"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh scored "limit=5"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh recommend "sort_by=stability&redeemable_only=true&limit=5"
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh summary "style=balanced"
```

