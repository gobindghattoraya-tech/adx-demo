-- Market Health Dashboard — Hello World seed migration
-- Idempotent: safe to run multiple times.

CREATE TABLE IF NOT EXISTS messages (
    id         SERIAL PRIMARY KEY,
    text       VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ  DEFAULT NOW()
);

-- Unique constraint on text so ON CONFLICT works
ALTER TABLE messages ADD CONSTRAINT messages_text_uq UNIQUE (text);

INSERT INTO messages (text)
VALUES ('Hello World')
ON CONFLICT (text) DO NOTHING;
