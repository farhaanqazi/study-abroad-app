# 🚀 Future Database Plan: From Booking Tool to SaaS Platform

## 📖 Executive Summary
**Vision:** Transform the Beauty Parlour Chatbot from a simple appointment scheduler into an industry-leading, multi-tenant SaaS platform.
**Core Shift:** Move from "storing bookings" to "tracking business events, money flow, and customer lifecycle."

---

## 🏗️ Architectural Philosophy
1.  **Snapshot Integrity:** Critical data (prices, staff) must be "frozen" at the moment of booking to ensure historical reporting accuracy.
2.  **Financial Decoupling:** Payments must be a separate layer to support partial payments, refunds, and reconciliation.
3.  **Line-Item Granularity:** Support mixed bills (Service + Product + Add-ons) via a POS-style line item structure.
4.  **Scalable Multi-Tenancy:** Every business-critical table must be scoped to `vendor_id`.

---

## 📅 Phase 1: Revenue Integrity (Immediate)
*Goal: Ensure the dashboard shows accurate revenue numbers regardless of future price changes.*

### 🔧 Database Changes
1.  **`appointments` Table:**
    *   Add `final_price DECIMAL(10,2)` (The price paid at booking).
2.  **Backfill Script:**
    *   Script to update existing appointments: `final_price = services.price`.
3.  **Booking Logic:**
    *   Update `create_appointment` to capture and save `final_price` atomically.

---

## 💰 Phase 2: Operational Reality (Next 1-2 Months)
*Goal: Model the real-world constraints of a busy vendor (Staff, Rooms, Money).*

### 1. Staff & Scheduling
*   **`staff` Table:** `id`, `vendor_id`, `name`, `role`, `commission_rate`, `phone`, `avatar_url`.
*   **`staff_availability` Table:** `staff_id`, `day_of_week`, `start_time`, `end_time`.
*   **`staff_services` Table:** `staff_id`, `service_id` (Qualifications).
*   **`appointments` Upgrade:** Add `staff_id`, `duration_minutes`.

### 2. Financials & POS
*   **`payments` Table:** `id`, `appointment_id`, `amount`, `method` (cash/card), `status`, `transaction_ref`.
*   **`appointment_line_items` Table:**
    *   `id`, `appointment_id`, `type` (service/product), `reference_id`, `quantity`, `unit_price`, `total`.
    *   *Why:* Allows selling shampoos/creams alongside haircuts in one transaction.

### 3. Resource Management
*   **`resources` Table:** `id`, `vendor_id`, `name` (e.g., "Color Room 1"), `type`, `capacity`.
*   **`appointments` Upgrade:** Add `resource_id` (Prevents double-booking rooms).

---

## 📈 Phase 3: Growth & Retention (Months 3-6)
*Goal: Tools to increase customer lifetime value and average ticket size.*

### 1. CRM & Loyalty
*   **`customers` Upgrade:** Add `lifetime_value`, `visit_count`, `no_show_count`, `preferred_staff_id`.
*   **`loyalty_points` Table:** `customer_id`, `balance`, `lifetime_earned`, `tier` (Bronze/Silver/Gold).
*   **`customer_tags` Table:** `id`, `customer_id`, `tag_name` (e.g., "VIP", "Bridal").

### 2. Inventory & Retail
*   **`products` Table:** `id`, `vendor_id`, `name`, `sku`, `cost_price`, `retail_price`, `stock_quantity`.
*   **`inventory_transactions` Table:** `id`, `product_id`, `type` (sale/restock), `quantity_change`, `reference_id`.

### 3. Marketing
*   **`marketing_campaigns` Table:** `id`, `name`, `type` (SMS/Email), `status`.
*   **`appointments` Upgrade:** Add `campaign_id`, `referral_code`.

---

## 🧠 Phase 4: Enterprise & AI (Long Term)
*Goal: Advanced features for vendor chains and predictive analytics.*

### 1. Multi-Location
*   **`vendor_groups` Table:** `id`, `name`, `owner_id` (Franchise support).
*   **`vendors` Upgrade:** Add `group_id`, `manager_id`.

### 2. AI & Intelligence
*   **`conversation_events` Table:** `id`, `session_id`, `intent`, `confidence`, `bot_response_time`.
*   **`customer_behavior` Table:** `customer_id`, `churn_risk_score`, `preferred_time_slot`, `avg_spend`.

---

## 🛡️ Phase 5: Control & Audit
*Goal: Enterprise-grade security and compliance.*

*   **`audit_logs` Table:** `id`, `actor_id`, `action`, `entity_type`, `entity_id`, `changes` (JSONB), `timestamp`.
*   **`feature_flags` Table:** `vendor_id`, `feature_name`, `is_enabled` (Controlled rollouts).

---

## 🚀 Execution Strategy

### Immediate Action (Today)
1.  Execute **Phase 1** (Revenue Integrity) to fix the dashboard metrics.

### Next Sprint
1.  Draft SQL for **Phase 2** (Staff & Payments).
2.  Update API endpoints to support `staff_id` in bookings.

### Review Checklist
*   [ ] Does every table have `created_at` and `updated_at`?
*   [ ] Is every sensitive table scoped by `vendor_id`?
*   [ ] Are financial columns using `DECIMAL` (not `FLOAT`)?
*   [ ] Do we have indexes on foreign keys?

---

**Status:** 🟢 Planning Phase
**Last Updated:** 2026-04-11
