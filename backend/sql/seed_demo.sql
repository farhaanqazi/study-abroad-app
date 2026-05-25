-- ============================================================
-- Beauty Parlour Chatbot — Demo Seed Data v2.0
-- Run AFTER migration_v2.sql completes successfully
-- ============================================================

BEGIN;

-- ============================================================
-- 1. CREATE DEMO VENDOR
-- ============================================================
INSERT INTO vendors (
    name, 
    slug, 
    timezone, 
    flow_config, 
    opening_time,
    closing_time,
    digest_preference,
    digest_time,
    currency
)
VALUES (
    'Demo Beauty Palace',
    'demo-beauty-palace',
    'Asia/Kolkata',
    '{"ask_sample_images": true, "greeting": "Welcome to Demo Beauty Palace!"}'::jsonb,
    '09:00:00'::time,  -- Opening time
    '20:00:00'::time,  -- Closing time
    'daily'::digest_preference,
    '09:00:00'::time,  -- Digest time
    'INR'
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    timezone = EXCLUDED.timezone,
    opening_time = EXCLUDED.opening_time,
    closing_time = EXCLUDED.closing_time,
    updated_at = now();

-- ============================================================
-- 2. CREATE CHANNEL CONFIGURATIONS
-- ============================================================
INSERT INTO vendor_channels (vendor_id, channel, provider_config, is_active)
SELECT id, 'telegram', '{"bot_name": "DemoBeautyBot"}'::jsonb, true
FROM vendors
WHERE slug = 'demo-beauty-palace'
ON CONFLICT (vendor_id, channel) DO UPDATE SET
    provider_config = EXCLUDED.provider_config,
    is_active = EXCLUDED.is_active,
    updated_at = now();

INSERT INTO vendor_channels (vendor_id, channel, provider_config, is_active)
SELECT id, 'whatsapp', '{"business_phone": "919999999999"}'::jsonb, true
FROM vendors
WHERE slug = 'demo-beauty-palace'
ON CONFLICT (vendor_id, channel) DO UPDATE SET
    provider_config = EXCLUDED.provider_config,
    is_active = EXCLUDED.is_active,
    updated_at = now();

-- ============================================================
-- 3. CREATE NOTIFICATION CONTACTS
-- ============================================================
INSERT INTO vendor_notification_contacts (vendor_id, name, channel, destination, is_active)
SELECT id, 'Owner Telegram', 'telegram', '123456789', true
FROM vendors
WHERE slug = 'demo-beauty-palace'
ON CONFLICT (vendor_id, channel, destination) DO UPDATE SET
    name = EXCLUDED.name,
    is_active = EXCLUDED.is_active,
    updated_at = now();

INSERT INTO vendor_notification_contacts (vendor_id, name, channel, destination, is_active)
SELECT id, 'Manager WhatsApp', 'whatsapp', '919876543210', true
FROM vendors
WHERE slug = 'demo-beauty-palace'
ON CONFLICT (vendor_id, channel, destination) DO UPDATE SET
    name = EXCLUDED.name,
    is_active = EXCLUDED.is_active,
    updated_at = now();

-- ============================================================
-- 4. CREATE SERVICES WITH PRICING
-- ============================================================
INSERT INTO vendor_services (
    vendor_id, 
    code, 
    name, 
    description, 
    duration_minutes,
    price,
    discount_price,
    sample_image_urls
)
SELECT
    id,
    'bridal_makeup',
    'Bridal Makeup',
    'Complete bridal makeup package including trial session',
    180,  -- 3 hours
    15000.00,  -- Price in INR
    12000.00,  -- Discount price
    '["https://example.com/bridal-1.jpg", "https://example.com/bridal-2.jpg"]'::jsonb
FROM vendors
WHERE slug = 'demo-beauty-palace'
ON CONFLICT (vendor_id, code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    duration_minutes = EXCLUDED.duration_minutes,
    price = EXCLUDED.price,
    discount_price = EXCLUDED.discount_price,
    sample_image_urls = EXCLUDED.sample_image_urls,
    updated_at = now();

INSERT INTO vendor_services (
    vendor_id, 
    code, 
    name, 
    description, 
    duration_minutes,
    price,
    discount_price,
    sample_image_urls
)
SELECT
    id,
    'engagement_makeup',
    'Engagement Makeup',
    'Elegant makeup for engagement ceremonies',
    120,  -- 2 hours
    8000.00,
    6500.00,
    '["https://example.com/engagement-1.jpg", "https://example.com/engagement-2.jpg"]'::jsonb
FROM vendors
WHERE slug = 'demo-beauty-palace'
ON CONFLICT (vendor_id, code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    duration_minutes = EXCLUDED.duration_minutes,
    price = EXCLUDED.price,
    discount_price = EXCLUDED.discount_price,
    sample_image_urls = EXCLUDED.sample_image_urls,
    updated_at = now();

INSERT INTO vendor_services (
    vendor_id, 
    code, 
    name, 
    description, 
    duration_minutes,
    price,
    discount_price,
    sample_image_urls
)
SELECT
    id,
    'party_makeup',
    'Party Makeup',
    'Glamorous makeup for parties and events',
    90,  -- 1.5 hours
    5000.00,
    4000.00,
    '["https://example.com/party-1.jpg"]'::jsonb
FROM vendors
WHERE slug = 'demo-beauty-palace'
ON CONFLICT (vendor_id, code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    duration_minutes = EXCLUDED.duration_minutes,
    price = EXCLUDED.price,
    discount_price = EXCLUDED.discount_price,
    sample_image_urls = EXCLUDED.sample_image_urls,
    updated_at = now();

INSERT INTO vendor_services (
    vendor_id, 
    code, 
    name, 
    description, 
    duration_minutes,
    price,
    discount_price,
    sample_image_urls
)
SELECT
    id,
    'hair_styling',
    'Hair Styling',
    'Professional hair styling and blowout',
    60,  -- 1 hour
    3000.00,
    2500.00,
    '["https://example.com/hair-1.jpg", "https://example.com/hair-2.jpg"]'::jsonb
FROM vendors
WHERE slug = 'demo-beauty-palace'
ON CONFLICT (vendor_id, code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    duration_minutes = EXCLUDED.duration_minutes,
    price = EXCLUDED.price,
    discount_price = EXCLUDED.discount_price,
    sample_image_urls = EXCLUDED.sample_image_urls,
    updated_at = now();

INSERT INTO vendor_services (
    vendor_id, 
    code, 
    name, 
    description, 
    duration_minutes,
    price,
    discount_price,
    sample_image_urls
)
SELECT
    id,
    'facial_treatment',
    'Facial Treatment',
    'Premium facial with cleansing and moisturizing',
    90,  -- 1.5 hours
    4500.00,
    3500.00,
    '[]'::jsonb
FROM vendors
WHERE slug = 'demo-beauty-palace'
ON CONFLICT (vendor_id, code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    duration_minutes = EXCLUDED.duration_minutes,
    price = EXCLUDED.price,
    discount_price = EXCLUDED.discount_price,
    sample_image_urls = EXCLUDED.sample_image_urls,
    updated_at = now();

-- ============================================================
-- 5. CREATE DEMO CUSTOMER
-- ============================================================
INSERT INTO customers (
    vendor_id,
    channel,
    external_user_id,
    phone_number,
    telegram_chat_id,
    name,
    language_preference
)
SELECT
    id,
    'whatsapp'::channel_type,
    '919123456789',
    '919123456789',
    NULL,
    'Priya Sharma',
    'english'
FROM vendors
WHERE slug = 'demo-beauty-palace'
ON CONFLICT (vendor_id, channel, external_user_id) DO UPDATE SET
    name = EXCLUDED.name,
    language_preference = EXCLUDED.language_preference,
    updated_at = now();

-- ============================================================
-- 6. CREATE DEMO APPOINTMENT (Future Date)
-- ============================================================
INSERT INTO appointments (
    vendor_id,
    customer_id,
    service_id,
    appointment_at,
    status,
    notes
)
SELECT
    s.id,
    c.id,
    srv.id,
    now() + interval '3 days' + interval '10 hours',  -- 3 days from now at 10 AM
    'confirmed'::appointment_status,
    'Demo appointment for testing'
FROM vendors s
CROSS JOIN customers c
CROSS JOIN vendor_services srv
WHERE s.slug = 'demo-beauty-palace'
  AND c.external_user_id = '919123456789'
  AND srv.code = 'bridal_makeup'
ON CONFLICT DO NOTHING;

-- ============================================================
-- 7. CREATE DEMO NOTIFICATION JOBS
-- ============================================================
INSERT INTO notification_jobs (
    appointment_id,
    vendor_id,
    job_type,
    status,
    due_at
)
SELECT
    a.id,
    a.vendor_id,
    'reminder_24h'::notification_job_type,
    'pending'::notification_job_status,
    a.appointment_at - interval '24 hours'
FROM appointments a
WHERE a.vendor_id = (SELECT id FROM vendors WHERE slug = 'demo-beauty-palace')
  AND a.appointment_at > now()
ON CONFLICT (appointment_id, job_type) DO UPDATE SET
    due_at = EXCLUDED.due_at,
    updated_at = now();

INSERT INTO notification_jobs (
    appointment_id,
    vendor_id,
    job_type,
    status,
    due_at
)
SELECT
    a.id,
    a.vendor_id,
    'reminder_1h'::notification_job_type,
    'pending'::notification_job_status,
    a.appointment_at - interval '1 hour'
FROM appointments a
WHERE a.vendor_id = (SELECT id FROM vendors WHERE slug = 'demo-beauty-palace')
  AND a.appointment_at > now()
ON CONFLICT (appointment_id, job_type) DO UPDATE SET
    due_at = EXCLUDED.due_at,
    updated_at = now();

-- ============================================================
-- 8. CREATE DEMO VENDOR CLOSURE (For Testing)
-- ============================================================
INSERT INTO vendor_closures (
    vendor_id,
    closed_from,
    closed_until,
    reason,
    notifications_queued
)
SELECT
    id,
    now() + interval '7 days',  -- Start closure in 7 days
    now() + interval '10 days',  -- End closure in 10 days
    'Annual maintenance closure',
    false
FROM vendors
WHERE slug = 'demo-beauty-palace'
ON CONFLICT DO NOTHING;

-- ============================================================
-- 9. CREATE DEMO USERS (Admin + Vendor Owner + Reception)
-- ============================================================
-- IMPORTANT: These steps create users in BOTH Supabase Auth AND the users table.
-- You must replace <uuid> values with actual UUIDs from Supabase Auth after creating accounts.
--
-- Step 1: Go to Supabase Dashboard → Authentication → Users
-- Step 2: Create these 3 users with the passwords listed:
--   • owner@demobeauty.com  —  password: owner123
--   • admin@demobeauty.com  —  password: admin123
--   • reception@demobeauty.com — password: reception123
-- Step 3: Copy each User ID (UUID) from Auth → Users
-- Step 4: Uncomment the INSERT statements below and replace <uuid> with actual UUIDs:
--
-- -- VENDOR OWNER (linked to Demo Beauty Palace)
-- INSERT INTO users (id, email, full_name, role, vendor_id, is_active)
-- VALUES (
--     '<uuid-from-auth-for-owner>',
--     'owner@demobeauty.com',
--     'Vendor Owner',
--     'vendor_owner',
--     (SELECT id FROM vendors WHERE slug = 'demo-beauty-palace'),
--     TRUE
-- );
--
-- -- ADMIN (can access all vendors)
-- INSERT INTO users (id, email, full_name, role, vendor_id, is_active)
-- VALUES (
--     '<uuid-from-auth-for-admin>',
--     'admin@demobeauty.com',
--     'Demo Admin',
--     'admin',
--     NULL,
--     TRUE
-- );
--
-- -- RECEPTION (linked to Demo Beauty Palace)
-- INSERT INTO users (id, email, full_name, role, vendor_id, is_active)
-- VALUES (
--     '<uuid-from-auth-for-reception>',
--     'reception@demobeauty.com',
--     'Front Desk',
--     'reception',
--     (SELECT id FROM vendors WHERE slug = 'demo-beauty-palace'),
--     TRUE
-- );
-- ============================================================

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================
-- Run these to verify seed data was created:

SELECT 'Vendors' as table_name, count(*) as count FROM vendors;
SELECT 'Services' as table_name, count(*) as count FROM vendor_services WHERE vendor_id = (SELECT id FROM vendors WHERE slug = 'demo-beauty-palace');
SELECT 'Customers' as table_name, count(*) as count FROM customers;
SELECT 'Appointments' as table_name, count(*) as count FROM appointments;
SELECT 'Notification Jobs' as table_name, count(*) as count FROM notification_jobs;
SELECT 'Vendor Closures' as table_name, count(*) as count FROM vendor_closures;

-- List demo services with pricing
SELECT 
    name,
    duration_minutes,
    price,
    discount_price,
    CASE WHEN discount_price IS NOT NULL 
         THEN round(((price - discount_price) / price * 100)::numeric, 0) 
         ELSE 0 
    END as discount_percent
FROM vendor_services
WHERE vendor_id = (SELECT id FROM vendors WHERE slug = 'demo-beauty-palace')
ORDER BY name;

-- ============================================================
-- END OF SEED DATA
-- ============================================================
