# SQL Migration Scripts — Beauty Parlour Chatbot v2.0

## File Overview

| File | Purpose | When to Run |
|------|---------|-------------|
| `migration_v2.sql` | Complete schema migration v1 → v2 | **Once** during initial Supabase setup |
| `seed_demo.sql` | Demo data for testing | After migration, for dev/staging environments |
| `verify_migration.sql` | Verify migration succeeded | Immediately after migration |
| `rollback_v2.sql` | Revert to v1 schema | **Only** if migration fails catastrophically |

---

## Quick Start (Supabase)

### Step 1: Create Supabase Project

1. Go to https://supabase.com
2. Create new project
3. Wait for database to provision (~2 minutes)
4. Note your project URL: `https://xxxxx.supabase.co`

### Step 2: Run Migration

1. Open Supabase SQL Editor (Dashboard → SQL Editor)
2. Copy entire contents of `migration_v2.sql`
3. Paste and click **Run**
4. Wait for completion (~10-15 seconds)
5. Verify: Should show "Success. No rows returned"

### Step 3: Verify Migration

1. Open SQL Editor again
2. Copy contents of `verify_migration.sql`
3. Run and check results:
   - **Tables:** Should show 13+
   - **RLS-Enabled Tables:** Should show 13
   - **Policies:** Should show 40+
   - **Triggers:** Should show 9

### Step 4: Seed Demo Data (Optional)

For dev/staging environments:

1. Copy contents of `seed_demo.sql`
2. Run in SQL Editor
3. Verify demo data created (vendor, services, sample appointment)

### Step 5: Create First Admin User

1. Go to **Authentication → Users** in Supabase Dashboard
2. Click **Add User** → Create with email/password
3. Copy the **User ID** (UUID format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
4. Open SQL Editor and run:

```sql
INSERT INTO users (id, email, full_name, role, vendor_id, is_active, created_by)
VALUES (
    'YOUR-UUID-HERE',  -- Replace with copied UUID
    'admin@demobeauty.com',
    'Demo Admin',
    'admin',
    (SELECT id FROM vendors WHERE slug = 'demo-beauty-palace'),
    TRUE,
    NULL
);
```

---

## Migration Checklist

Before running migration:

- [ ] Supabase project created
- [ ] Database connection tested
- [ ] Backup of existing data (if migrating from v1)
- [ ] Team notified of maintenance window
- [ ] Backend `.env` ready for `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`

After running migration:

- [ ] `verify_migration.sql` shows all checks passing
- [ ] First admin user created in `users` table
- [ ] Demo data seeded (if applicable)
- [ ] Backend updated with Supabase credentials
- [ ] Test appointment booking flow works

---

## Rollback Procedure

**⚠️ WARNING:** Only rollback if migration fails catastrophically. This will destroy all v2 data.

1. Open SQL Editor
2. Copy contents of `rollback_v2.sql`
3. Run and confirm
4. Verify v1 schema is intact:
   ```sql
   SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
   ```

**Note:** ENUM values cannot be fully removed without recreating the type. If you need to revert enums, contact a database administrator.

---

## Table Reference (v2)

| Table | Purpose | RLS Enabled |
|-------|---------|-------------|
| `vendors` | Tenant configuration | ✓ |
| `users` | Dashboard authentication | ✓ |
| `vendor_channels` | WhatsApp/Telegram config | ✓ |
| `vendor_services` | Service catalog with pricing | ✓ |
| `customers` | User profiles from chat | ✓ |
| `appointments` | Bookings | ✓ |
| `notification_jobs` | Reminder queue | ✓ |
| `vendor_closures` | Closure audit log | ✓ |
| `appointment_status_log` | Status change history | ✓ |
| `inbound_messages` | Incoming message log | ✓ |
| `outbound_messages` | Outgoing message log | ✓ |
| `vendor_notification_contacts` | Staff contacts | ✓ |
| `schema_migrations` | Migration version tracking | ✗ |

---

## RLS Policy Summary

| Role | Access Level |
|------|--------------|
| `admin` | Full CRUD on all tables |
| `vendor_owner` | Read/Write own vendor data only |
| `reception` | Read/Write appointments & services for own vendor |

**Backend Access:** Uses Supabase Service Role Key which **bypasses RLS entirely**. Never expose this key to frontend.

---

## Common Issues

### Issue: "relation already exists"

**Cause:** Running migration on database that already has v1 tables.

**Fix:** Migration uses `IF NOT EXISTS` — safe to run. Warnings are normal.

### Issue: "enum value already exists"

**Cause:** Re-running migration after partial failure.

**Fix:** Migration uses `ADD VALUE IF NOT EXISTS` — safe to continue.

### Issue: "violates foreign key constraint"

**Cause:** Seed data references vendor that doesn't exist.

**Fix:** Run `migration_v2.sql` first, then `seed_demo.sql`.

### Issue: "permission denied for table"

**Cause:** RLS blocking access after migration.

**Fix:** 
1. Verify user exists in `users` table with correct role
2. Check RLS policies: `SELECT * FROM pg_policies WHERE schemaname = 'public'`
3. For backend: Use Service Role Key

### Issue: "function auth.uid() does not exist"

**Cause:** Running outside Supabase environment.

**Fix:** This schema is designed for Supabase only. For self-hosted PostgreSQL, you'll need custom auth.

---

## Environment Variables (Backend)

After migration, update backend `.env`:

```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Keep existing
DATABASE_URL=postgresql+asyncpg://postgres:password@db.xxx.supabase.co:5432/postgres
REDIS_URL=redis://localhost:6379/0
```

---

## Support

For issues:
1. Check `verify_migration.sql` output
2. Review Supabase logs (Dashboard → Logs)
3. Consult rollback procedure if needed
4. Contact team database administrator

---

**Last Updated:** March 16, 2026  
**Schema Version:** 2.0  
**Compatible With:** Supabase PostgreSQL 15+
