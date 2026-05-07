-- V003: Symbols — master list of all tradable assets
CREATE TABLE IF NOT EXISTS symbols (
    symbol_id     BIGSERIAL      PRIMARY KEY,
    ticker_symbol VARCHAR(20)    UNIQUE NOT NULL,
    full_name     VARCHAR(255)   NOT NULL,
    sector_id     BIGINT         NOT NULL REFERENCES sectors(sector_id),
    tick_size     NUMERIC(18, 8) NOT NULL CHECK (tick_size > 0),
    lot_size      INTEGER        NOT NULL CHECK (lot_size > 0),
    currency      CHAR(3)        NOT NULL,
    is_active     BOOLEAN        NOT NULL DEFAULT TRUE,
    updated_at    TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);
