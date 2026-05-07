-- V005: Trades — immutable ledger of all matched order executions
CREATE TABLE IF NOT EXISTS trades (
    trade_id           BIGSERIAL      PRIMARY KEY,
    symbol_id          BIGINT         NOT NULL REFERENCES symbols(symbol_id),
    buy_order_id       BIGINT         NOT NULL REFERENCES order_books(order_id),
    sell_order_id      BIGINT         NOT NULL REFERENCES order_books(order_id),
    execution_price    NUMERIC(18, 8) NOT NULL CHECK (execution_price > 0),
    execution_quantity NUMERIC(18, 8) NOT NULL CHECK (execution_quantity > 0),
    total_value        NUMERIC(18, 8) NOT NULL,
    executed_at        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    -- Financial integrity: total_value must equal price * quantity (1e-8 tolerance)
    CONSTRAINT chk_total_value CHECK (
        ABS(total_value - (execution_price * execution_quantity)) < 1e-8
    ),
    -- Prevent self-trades (buy and sell must be different orders)
    CONSTRAINT chk_different_orders CHECK (buy_order_id != sell_order_id)
);
