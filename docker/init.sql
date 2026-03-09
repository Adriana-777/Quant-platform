-- 行情数据表（Tick 级别）
CREATE TABLE IF NOT EXISTS ticks (
    id          BIGSERIAL PRIMARY KEY,
    symbol      VARCHAR(20)  NOT NULL,
    exchange    VARCHAR(20)  NOT NULL,
    timestamp   TIMESTAMPTZ  NOT NULL,
    open        NUMERIC(20, 8),
    high        NUMERIC(20, 8),
    low         NUMERIC(20, 8),
    close       NUMERIC(20, 8),
    volume      NUMERIC(20, 8)
);

-- 按时间分区索引，查询历史数据时快很多
CREATE INDEX IF NOT EXISTS idx_ticks_symbol_ts ON ticks (symbol, timestamp DESC);

-- 订单记录表
CREATE TABLE IF NOT EXISTS orders (
    id           BIGSERIAL PRIMARY KEY,
    strategy_id  VARCHAR(50),
    symbol       VARCHAR(20) NOT NULL,
    side         VARCHAR(4)  NOT NULL,  -- BUY / SELL
    order_type   VARCHAR(10) NOT NULL,
    quantity     NUMERIC(20, 8),
    price        NUMERIC(20, 8),
    status       VARCHAR(10) DEFAULT 'PENDING',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 成交记录表
CREATE TABLE IF NOT EXISTS fills (
    id           BIGSERIAL PRIMARY KEY,
    order_id     BIGINT REFERENCES orders(id),
    symbol       VARCHAR(20)  NOT NULL,
    side         VARCHAR(4)   NOT NULL,
    quantity     NUMERIC(20, 8),
    fill_price   NUMERIC(20, 8),
    commission   NUMERIC(20, 8),
    filled_at    TIMESTAMPTZ  DEFAULT NOW()
);

-- 策略绩效快照表
CREATE TABLE IF NOT EXISTS performance_snapshots (
    id           BIGSERIAL PRIMARY KEY,
    strategy_id  VARCHAR(50),
    timestamp    TIMESTAMPTZ DEFAULT NOW(),
    equity       NUMERIC(20, 8),
    drawdown     NUMERIC(10, 6),
    sharpe       NUMERIC(10, 6),
    total_trades INT
);
