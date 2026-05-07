-- V002: Sectors — market segment categorisation (reference data)
CREATE TABLE IF NOT EXISTS sectors (
    sector_id   BIGSERIAL    PRIMARY KEY,
    sector_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
