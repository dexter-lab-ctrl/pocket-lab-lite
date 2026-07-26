-- Persisted command reconciliation and explicit attention acknowledgement.
ALTER TABLE command_lifecycle ADD COLUMN attention_status TEXT NOT NULL DEFAULT 'none'
    CHECK (attention_status IN ('none', 'active', 'acknowledged'));
ALTER TABLE command_lifecycle ADD COLUMN attention_updated_at TEXT;
ALTER TABLE command_lifecycle ADD COLUMN attention_updated_at_epoch_ms INTEGER NOT NULL DEFAULT 0;

UPDATE command_lifecycle
SET attention_status = 'active',
    attention_updated_at = COALESCE(terminal_at, updated_at),
    attention_updated_at_epoch_ms = updated_at_epoch_ms
WHERE status IN ('failed', 'undeliverable', 'timed_out');

CREATE INDEX IF NOT EXISTS idx_commands_attention_latest
    ON command_lifecycle(attention_status, updated_at_epoch_ms DESC, command_id DESC);
CREATE INDEX IF NOT EXISTS idx_commands_nonterminal_age
    ON command_lifecycle(status, updated_at_epoch_ms ASC, command_id ASC)
    WHERE terminal_at IS NULL;
