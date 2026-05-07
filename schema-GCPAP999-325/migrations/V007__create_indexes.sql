-- V007: Performance indexes for matching engine and user queries
-- order_books: full symbol scan + active-only partial index
CREATE INDEX IF NOT EXISTS idx_order_books_symbol_id
    ON order_books(symbol_id);

CREATE INDEX IF NOT EXISTS idx_order_books_status
    ON order_books(order_status);

-- Partial index: active orders only — dramatically reduces index size for the matching engine
CREATE INDEX IF NOT EXISTS idx_order_books_sym_open
    ON order_books(symbol_id, order_status)
    WHERE order_status = 'OPEN';

-- trades: symbol timeline queries
CREATE INDEX IF NOT EXISTS idx_trades_symbol_id
    ON trades(symbol_id);

CREATE INDEX IF NOT EXISTS idx_trades_executed_at
    ON trades(executed_at DESC);

-- watchlists: user and symbol lookups
CREATE INDEX IF NOT EXISTS idx_watchlists_user_id
    ON watchlists(user_id);

CREATE INDEX IF NOT EXISTS idx_watchlists_symbol_id
    ON watchlists(symbol_id);
