-- V001: Create ENUM types
-- These must be created before the tables that reference them.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'order_side') THEN
        CREATE TYPE order_side AS ENUM ('BID', 'OFFER');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'order_status_type') THEN
        CREATE TYPE order_status_type AS ENUM ('OPEN', 'PARTIAL', 'FILLED', 'CANCELLED');
    END IF;
END $$;
