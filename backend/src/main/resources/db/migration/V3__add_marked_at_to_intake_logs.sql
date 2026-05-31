-- Migration: add marked_at to intake_logs
-- Created: 2026-05-08

ALTER TABLE medications.intake_logs
    ADD COLUMN IF NOT EXISTS marked_at TIMESTAMP WITH TIME ZONE NULL;

CREATE INDEX IF NOT EXISTS idx_intake_logs_marked_at ON medications.intake_logs(marked_at);

-- No backfill performed; existing rows will have NULL marked_at until user action.
