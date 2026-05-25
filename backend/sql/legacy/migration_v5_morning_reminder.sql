-- ============================================================
-- Migration v5: 7 AM Morning-Of Appointment Reminder
-- ============================================================
-- Adds the 'reminder_7am' value to the notification_job_type
-- PostgreSQL enum and backfills REMINDER_7AM jobs for all
-- future confirmed appointments that don't already have one.
--
-- ⚠️  IMPORTANT — Run in two separate steps in Supabase SQL editor:
--
--   STEP A (no transaction block — ALTER TYPE cannot run inside BEGIN):
--     Run the ALTER TYPE statement below by itself first.
--
--   STEP B (inside a transaction — BEGIN/COMMIT):
--     Run the rest of the script (backfill + trigger update).
--
-- Why two steps?  PostgreSQL does not allow ALTER TYPE ... ADD VALUE
-- inside a transaction block that has already executed other statements.
-- ============================================================


-- ============================================================
-- STEP A — Add enum value (run ALONE, no BEGIN/COMMIT wrapper)
-- ============================================================

ALTER TYPE notification_job_type ADD VALUE IF NOT EXISTS 'reminder_7am';


-- ============================================================
-- STEP B — Backfill 7 AM jobs for all future appointments
-- ============================================================
-- Run after STEP A has been committed.
-- ============================================================

BEGIN;

-- ----------------------------------------------------------
-- Insert REMINDER_7AM jobs for every confirmed/pending
-- appointment in the future that does not yet have one.
--
-- due_at is calculated as 07:00:00 local vendor time on the
-- appointment's date, stored in UTC.
--
-- The ON CONFLICT DO NOTHING guard is a safety net —
-- the unique constraint (appointment_id, job_type) prevents
-- duplicate jobs from being created on re-runs.
-- ----------------------------------------------------------

INSERT INTO notification_jobs (
    id,
    appointment_id,
    vendor_id,
    job_type,
    status,
    due_at,
    attempts,
    payload,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid()                                          AS id,
    a.id                                                       AS appointment_id,
    a.vendor_id                                                 AS vendor_id,
    'reminder_7am'::notification_job_type                      AS job_type,
    'pending'::notification_job_status                         AS status,
    -- Convert appointment date to vendor local time, pin to 07:00, convert back to UTC
    (DATE_TRUNC('day', a.appointment_at AT TIME ZONE COALESCE(s.timezone, 'Asia/Kolkata'))
     + INTERVAL '7 hours')
    AT TIME ZONE COALESCE(s.timezone, 'Asia/Kolkata')         AS due_at,
    0                                                          AS attempts,
    '{"reminder_type": "morning_of"}'::jsonb                   AS payload,
    NOW()                                                      AS created_at,
    NOW()                                                      AS updated_at
FROM appointments a
JOIN vendors s ON s.id = a.vendor_id
WHERE
    -- Only future appointments
    a.appointment_at > NOW()
    -- Only active statuses
    AND a.status IN ('confirmed'::appointment_status, 'pending'::appointment_status)
    -- Only if the 7 AM time itself is still in the future
    AND (
        DATE_TRUNC('day', a.appointment_at AT TIME ZONE COALESCE(s.timezone, 'Asia/Kolkata'))
        + INTERVAL '7 hours'
    ) AT TIME ZONE COALESCE(s.timezone, 'Asia/Kolkata') > NOW()
    -- Don't duplicate if already scheduled
    AND NOT EXISTS (
        SELECT 1
        FROM notification_jobs nj
        WHERE nj.appointment_id = a.id
          AND nj.job_type = 'reminder_7am'::notification_job_type
    )
ON CONFLICT (appointment_id, job_type) DO NOTHING;

-- Report backfill count
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'migration_v5: % morning reminder jobs scheduled.', v_count;
END $$;

COMMIT;


-- ============================================================
-- VERIFICATION QUERIES (run manually after migration)
-- ============================================================

-- Count scheduled 7 AM jobs:
-- SELECT COUNT(*) FROM notification_jobs WHERE job_type = 'reminder_7am';

-- Preview the scheduled reminders (first 20):
-- SELECT
--     a.booking_reference,
--     a.appointment_at,
--     nj.due_at,
--     nj.status
-- FROM notification_jobs nj
-- JOIN appointments a ON a.id = nj.appointment_id
-- WHERE nj.job_type = 'reminder_7am'
-- ORDER BY nj.due_at
-- LIMIT 20;
