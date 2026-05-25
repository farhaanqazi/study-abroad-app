-- ============================================================
-- Migration v4: Auto-complete past appointments
-- ============================================================
-- Context: Appointments that are past their scheduled time but
-- still sitting in 'confirmed', 'pending', or 'in_progress'
-- status should be transitioned to 'completed'.
--
-- This migration:
--   1. Batch-updates all existing stale past appointments.
--   2. Creates a DB function + trigger to auto-complete new ones
--      so the dashboard shows correct counts immediately.
--
-- Safe to run multiple times (idempotent WHERE clause).
-- Run OUTSIDE a transaction block when using ADD VALUE,
-- but this script has no ALTER TYPE so it is fully transactional.
-- ============================================================

BEGIN;

-- ----------------------------------------------------------------
-- STEP 1 ─ Backfill: mark all past appointments as completed
-- ----------------------------------------------------------------
-- Only transitions statuses that represent a "still scheduled but
-- missed" appointment.  Explicitly skipped:
--   cancelled_by_client, cancelled_by_vendor, cancelled_by_reception,
--   cancelled_closure, cancelled_by_user, no_show
-- because those have intentional terminal statuses.
--
-- GET DIAGNOSTICS ROW_COUNT only works inside the same PL/pgSQL
-- block as the DML, so the UPDATE lives inside the DO $$ block.
-- ----------------------------------------------------------------

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE appointments
    SET
        status     = 'completed'::appointment_status,
        updated_at = NOW() AT TIME ZONE 'UTC'
    WHERE
        appointment_at < (NOW() AT TIME ZONE 'UTC')
        AND status IN (
            'confirmed'::appointment_status,
            'pending'::appointment_status,
            'in_progress'::appointment_status
        );

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'migration_v4: % appointments auto-completed.', v_count;
END $$;

-- ----------------------------------------------------------------
-- STEP 2 ─ DB Function: auto_complete_past_appointment()
-- ----------------------------------------------------------------
-- Called by the trigger below on every INSERT or UPDATE of an
-- appointment row.  If the scheduled time is already in the past
-- and the status is still an "active" value, flip it to completed.
-- This handles edge-cases where an appointment is created or
-- rescheduled to a datetime that is already past.
-- ----------------------------------------------------------------

CREATE OR REPLACE FUNCTION auto_complete_past_appointment()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.appointment_at < (NOW() AT TIME ZONE 'UTC')
       AND NEW.status IN (
           'confirmed'::appointment_status,
           'pending'::appointment_status,
           'in_progress'::appointment_status
       )
    THEN
        NEW.status := 'completed'::appointment_status;
    END IF;
    RETURN NEW;
END;
$$;

-- ----------------------------------------------------------------
-- STEP 3 ─ Trigger: fire before each row insert or update
-- ----------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_auto_complete_past_appointment ON appointments;

CREATE TRIGGER trg_auto_complete_past_appointment
    BEFORE INSERT OR UPDATE ON appointments
    FOR EACH ROW
    EXECUTE FUNCTION auto_complete_past_appointment();

COMMIT;

-- ================================================================
-- VERIFICATION QUERIES  (run manually to sanity-check the result)
-- ================================================================

-- Count by status after migration:
-- SELECT status, COUNT(*) FROM appointments GROUP BY status ORDER BY status;

-- Check that no past confirmed/pending appointments remain:
-- SELECT COUNT(*) FROM appointments
-- WHERE appointment_at < NOW() AND status IN ('confirmed','pending','in_progress');
