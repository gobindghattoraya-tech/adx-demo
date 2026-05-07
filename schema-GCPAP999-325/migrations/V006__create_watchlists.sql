-- V006: Watchlists — user-personalised symbol monitoring
-- user_id is BIGINT NOT NULL; FK constraint deferred until users table is created (separate ticket)
CREATE TABLE IF NOT EXISTS watchlists (
    watchlist_id          UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               BIGINT         NOT NULL,
    symbol_id             BIGINT         NOT NULL REFERENCES symbols(symbol_id),
    added_at              TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    alert_price_threshold NUMERIC(18, 8),

    -- A user can only watch a given symbol once
    CONSTRAINT uq_user_symbol UNIQUE (user_id, symbol_id)
);
