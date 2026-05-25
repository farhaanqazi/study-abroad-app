-- ============================================================
-- Migration v3: appointment lifecycle statuses
-- ============================================================
-- Adds 'in_progress' to the appointment_status PostgreSQL enum.
-- ALTER TYPE ... ADD VALUE is transactional in PostgreSQL 12+
-- but cannot run inside a transaction block that already modified
-- the type.  Run this script standalone (not inside BEGIN/COMMIT).
-- ============================================================

-- Add the new status value (idempotent — no-op if it already exists)
ALTER TYPE appointment_status ADD VALUE IF NOT EXISTS 'in_progress';

-- Make sure LIFECYCLE_POLL_SECONDS is set in your .env (default 600 s).
-- No table-level changes are needed; the worker updates rows in-place.
