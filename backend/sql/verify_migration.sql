-- ============================================================
-- Beauty Parlour Chatbot — Migration Verification Script v2.0
-- Run AFTER migration to verify everything is working
-- ============================================================

-- ============================================================
-- 1. TABLE COUNT VERIFICATION
-- ============================================================
SELECT 
    'Table Count' as check_name,
    count(*) as result,
    'Expected: 13+' as expected
FROM pg_tables 
WHERE schemaname = 'public';

-- ============================================================
-- 2. RLS ENABLED VERIFICATION
-- ============================================================
SELECT 
    'RLS Enabled' as check_name,
    tablename,
    rowsecurity as status,
    CASE WHEN rowsecurity THEN '✓' ELSE '✗ FAIL' END as result
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;

-- ============================================================
-- 3. POLICY COUNT VERIFICATION
-- ============================================================
SELECT 
    'Policy Count' as check_name,
    tablename,
    count(*) as policy_count,
    CASE WHEN count(*) >= 2 THEN '✓' ELSE '✗ FAIL' END as result
FROM pg_policies 
WHERE schemaname = 'public'
GROUP BY tablename
ORDER BY tablename;

-- ============================================================
-- 4. ENUM VALUES VERIFICATION
-- ============================================================
SELECT 
    'appointment_status Enum' as check_name,
    unnest(enum_range(NULL::appointment_status)) as values;

SELECT 
    'notification_job_type Enum' as check_name,
    unnest(enum_range(NULL::notification_job_type)) as values;

SELECT 
    'notification_job_status Enum' as check_name,
    unnest(enum_range(NULL::notification_job_status)) as values;

-- ============================================================
-- 5. TRIGGER VERIFICATION
-- ============================================================
SELECT 
    'Triggers' as check_name,
    tgname as trigger_name,
    tgrelid::regclass as table_name,
    CASE WHEN tgname LIKE '%status_log%' THEN '✓ Status Log Trigger' 
         WHEN tgname LIKE '%updated_at%' THEN '✓ Updated At Trigger'
         ELSE 'Other' 
    END as result
FROM pg_trigger
WHERE tgname LIKE '%status_log%' OR tgname LIKE '%updated_at%'
ORDER BY tgrelid::regclass::text, tgname;

-- ============================================================
-- 6. FOREIGN KEY VALIDATION
-- ============================================================
SELECT 
    'Foreign Keys' as check_name,
    conname as constraint_name,
    conrelid::regclass as table_name,
    confrelid::regclass as referenced_table,
    '✓ Valid' as result
FROM pg_constraint
WHERE contype = 'f'
AND connamespace = 'public'::regnamespace
ORDER BY conrelid::regclass::text;

-- ============================================================
-- 7. INDEX VERIFICATION
-- ============================================================
SELECT 
    'Indexes' as check_name,
    indexname,
    tablename,
    '✓ Created' as result
FROM pg_indexes
WHERE schemaname = 'public'
AND indexname LIKE 'idx_%'
ORDER BY tablename, indexname;

-- ============================================================
-- 8. HELPER FUNCTIONS VERIFICATION
-- ============================================================
SELECT 
    'Helper Functions' as check_name,
    proname as function_name,
    prosrc as source,
    CASE WHEN prosecdef THEN '✓ SECURITY DEFINER' ELSE 'Regular' END as security
FROM pg_proc
WHERE proname IN ('current_user_role', 'current_user_vendor_id', 'update_updated_at', 'log_appointment_status_change');

-- ============================================================
-- 9. DATA COUNT HEALTH CHECK
-- ============================================================
SELECT 
    'Data Counts' as check_name,
    (SELECT count(*) FROM vendors) as vendors,
    (SELECT count(*) FROM users) as users,
    (SELECT count(*) FROM vendor_services) as services,
    (SELECT count(*) FROM appointments) as appointments,
    (SELECT count(*) FROM customers) as customers,
    (SELECT count(*) FROM pg_policies WHERE schemaname = 'public') as policies;

-- ============================================================
-- 10. MIGRATION VERSION CHECK
-- ============================================================
SELECT 
    'Migration Version' as check_name,
    version,
    applied_at,
    description
FROM schema_migrations
ORDER BY version DESC;

-- ============================================================
-- 11. CRITICAL CONSTRAINTS CHECK
-- ============================================================
SELECT 
    'Constraints' as check_name,
    conname as constraint_name,
    conrelid::regclass as table_name,
    contype as type,
    '✓ Exists' as result
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
AND conname LIKE '%role_vendor_required%'
   OR conname LIKE '%uq_appointment_job_type%'
   OR conname LIKE '%uq_vendor_%';

-- ============================================================
-- 12. PRICE CONSTRAINT CHECK
-- ============================================================
SELECT 
    'Price Constraints' as check_name,
    conname as constraint_name,
    conrelid::regclass as table_name,
    pg_get_constraintdef(oid) as definition,
    '✓ Check constraint exists' as result
FROM pg_constraint
WHERE contype = 'c'
AND conrelid = 'vendor_services'::regclass
AND conname LIKE '%price%';

-- ============================================================
-- SUMMARY
-- ============================================================
SELECT '=== MIGRATION VERIFICATION SUMMARY ===' as message;

SELECT 
    'Tables: ' || count(*) as summary
FROM pg_tables WHERE schemaname = 'public';

SELECT 
    'RLS-Enabled Tables: ' || count(*) as summary
FROM pg_tables WHERE schemaname = 'public' AND rowsecurity = true;

SELECT 
    'RLS Policies: ' || count(*) as summary
FROM pg_policies WHERE schemaname = 'public';

SELECT 
    'Triggers: ' || count(*) as summary
FROM pg_trigger
WHERE tgname LIKE '%status_log%' OR tgname LIKE '%updated_at%';

SELECT 
    'Foreign Keys: ' || count(*) as summary
FROM pg_constraint
WHERE contype = 'f' AND connamespace = 'public'::regnamespace;

-- ============================================================
-- EXPECTED RESULTS
-- ============================================================
-- Tables: 13+ (including schema_migrations)
-- RLS-Enabled Tables: 13 (all business tables)
-- RLS Policies: 40+ (4 per table × 13 tables ≈ 52)
-- Triggers: 9 (8 updated_at + 1 status_log)
-- Foreign Keys: 20+
-- 
-- If any count is significantly lower, review migration logs
-- ============================================================
