# Quant Platform

多市场实时行情聚合与策略回测平台，支持 Binance（加密货币）和 Alpaca（美股）。

## 架构

```
交易所 WebSocket (Binance / Alpaca)
        ↓
    采集服务 (data/feeds/)
        ↓
      Kafka Topic
     ↙         ↘
Redis           PostgreSQL
(实时状态)      (历史数据)
     ↘         ↙
   策略引擎 (engine/)
        ↓
   监控平台 (monitor/)
```

## 快速开始

### 1. 启动基础服务
```bash
cd docker
docker-compose up -d
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

### 3. 安装依赖
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. 启动行情采集
```bash
python -m data.feeds.binance_feed
```

## 开发阶段

- [x] 阶段零：项目框架与目录结构
- [ ] 阶段一：行情数据采集（Binance & Alpaca WebSocket）
- [ ] 阶段二：数据存储层（Kafka + Redis + PostgreSQL）
- [ ] 阶段三：回测引擎（事件驱动）
- [ ] 阶段四：策略引擎（多策略并发）
- [ ] 阶段五：监控平台（Dash/Plotly）
