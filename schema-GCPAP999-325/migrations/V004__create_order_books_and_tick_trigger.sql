-- V004: Order Books — live liquidity state optimised for high-frequency updates
CREATE TABLE IF NOT EXISTS order_books (
    order_id           BIGSERIAL         PRIMARY KEY,
    symbol_id          BIGINT            NOT NULL REFERENCES symbols(symbol_id),
    side               order_side        NOT NULL,
    price              NUMERIC(18, 8)    NOT NULL CHECK (price > 0),
    quantity_original  NUMERIC(18, 8)    NOT NULL CHECK (quantity_original > 0),
    quantity_remaining NUMERIC(18, 8)    NOT NULL CHECK (quantity_remaining >= 0),
    order_status       order_status_type NOT NULL DEFAULT 'OPEN',
    placed_at          TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

-- Tick validation: enforce that price is a valid multiple of the symbol's tick_size
CREATE OR REPLACE FUNCTION validate_tick_size()
RETURNS TRIGGER AS $$
DECLARE
    sym_tick_size NUMERIC(18, 8);
BEGIN
    SELECT tick_size INTO sym_tick_size
    FROM symbols
    WHERE symbol_id = NEW.symbol_id;

    IF sym_tick_size IS NULL THEN
        RAISE EXCEPTION 'Symbol % not found in symbols table', NEW.symbol_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    -- Use modulo; tolerance of 1e-8 for floating point edge cases
    IF ABS(MOD(NEW.price::NUMERIC, sym_tick_size::NUMERIC)) > 1e-8 THEN
        RAISE EXCEPTION
            'Price % is not a valid multiple of tick_size % for symbol_id %',
            NEW.price, sym_tick_size, NEW.symbol_id
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_tick_size ON order_books;
CREATE TRIGGER trg_validate_tick_size
    BEFORE INSERT OR UPDATE OF price ON order_books
    FOR EACH ROW EXECUTE FUNCTION validate_tick_size();
