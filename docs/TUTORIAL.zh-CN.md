# Binance Alpha Finance Skill 中文教程

## 这是什么

这是一个可以直接放进 `OpenClaw` 使用的本地 skill，主要提供两类能力：

1. `Binance Alpha`
   - 4×积分代币稳定性分析
   - 波动率 / spread / score
   - alerts
   - 历史快照

2. `Binance Finance`
   - 理财产品列表
   - 活动列表
   - 理财历史快照
   - 按 `product_id` 查询单产品历史

## 适合谁

- 想把 Binance Alpha / Finance 接进 OpenClaw 的用户
- 想本地自托管 skill，而不是依赖第三方云接口的用户
- 想做自动化脚本、策略、监控的用户

## 安装方式

### 方式一：直接 clone 到 OpenClaw skills

```bash
git clone https://github.com/fadai216/binance-alpha-finance-skill.git ~/.openclaw/skills/binance-alpha-finance
```

### 方式二：先 clone 到任意目录，再安装

```bash
git clone https://github.com/fadai216/binance-alpha-finance-skill.git
cd binance-alpha-finance-skill
bash scripts/install.sh
```

## 首次启动

执行：

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/ensure_backend.sh
```

这一步会自动：

1. 创建 `backend/.venv`
2. 安装 Python 依赖
3. 启动 FastAPI 后端

如果 `8000` 端口已经有同一个后端在运行，并且 `/health` 可用，它会直接返回成功，不会重复报错。

## 常用查询

### 查询 Alpha 稳定性

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh alpha 'top=3'
```

### 查询 Alpha 历史

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh alpha-history 'limit=12'
```

### 查询理财产品

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh finance 'sort_by=apr&order=desc&product_type=all&limit=5'
```

### 查询活动列表

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh activity 'status=active&reward_type=all&limit=5'
```

### 按 product_id 查询单产品历史

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/query.sh finance-history 'product_id=activity:65317d61d1c445f99f73a04c05233dd2&limit=5'
```

## 返回字段重点

### 理财产品字段

- `product_id`
  - 稳定唯一 ID
- `product_name`
  - 产品名
- `product_type`
  - `flexible | locked | activity`
- `apr`
  - 年化收益率
- `term_days`
  - 期限
- `source`
  - 来源标签

### source 说明

- `signed-sapi`
  - 官方 Binance Simple Earn signed API
- `activity-derived`
  - 从币安活动公告里派生出来的理财产品
- `public-finance-fallback`
  - 回退链路或旧快照补全

## 如何拿完整官方理财池

默认情况下，如果没有配置 API key，skill 只能：

- 调 Binance 活动 CMS
- 解析活动详情
- 派生活动型理财产品

如果你想优先走官方 Simple Earn signed API，需要配置：

```bash
export BINANCE_API_KEY="你的 key"
export BINANCE_API_SECRET="你的 secret"
```

然后重启后端：

```bash
bash ~/.openclaw/skills/binance-alpha-finance/scripts/ensure_backend.sh
```

## OpenClaw 里怎么用

这个 skill 是后端型 skill，不依赖前端页面。

你可以让 OpenClaw：

- 启动 skill 后端
- 调用 `query.sh`
- 直接读取本地 API 返回 JSON

推荐口令：

- 查 alpha 稳定性
- 查 finance 列表
- 查 finance activity
- 查某个 `product_id` 的 finance history

## 常见问题

### 1. `ensure_backend.sh` 报端口占用

如果健康检查成功，它现在会直接判定为“已可用”。

### 2. finance 里只有活动派生产品，没有完整理财池

说明你当前没配：

- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`

### 3. 历史查询为什么优先用 `product_id`

因为产品名可能变、文案可能变，`product_id` 更稳定，不容易串产品。

## 仓库文件说明

- `SKILL.md`
  - OpenClaw skill 主说明
- `config.json`
  - 本地 API 和路径配置
- `backend/`
  - FastAPI 后端源码
- `scripts/`
  - 启动、安装、查询脚本

## 升级

如果你从 GitHub 拉了新版本：

```bash
cd ~/.openclaw/skills/binance-alpha-finance
git pull
bash scripts/ensure_backend.sh
```

