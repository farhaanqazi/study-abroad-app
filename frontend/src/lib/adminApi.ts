// Platform back-office admin API client. Reuses the token-authed `consoleClient`
// (Clerk bearer injected via interceptor) from consoleApi.ts. All routes live
// under `${API_PREFIX}/admin` and require platform_role != 'none' server-side.
import { consoleClient, type PlatformRole } from './consoleApi';
import { API_PREFIX } from './api';

const adminBase = `${API_PREFIX}/admin`;

// ============================================================================
// Types — mirror backend app/schemas/{admin,ops,support,workspace}.py
// ============================================================================

export type VendorStatus = 'active' | 'suspended' | 'deleted';
export type MemberRole = 'owner' | 'agent' | 'viewer';
export type WorkspaceRequestStatus = 'pending' | 'approved' | 'rejected' | 'cancelled';
export type SupportTicketStatus = 'open' | 'pending' | 'resolved' | 'closed';

export interface PlatformOverview {
  vendors: { active: number; suspended: number; deleted: number; total: number };
  pending_workspace_requests: number;
  total_leads: number;
  outbox_failed: number;
  recent_signups_7d: number;
}

export interface AdminWorkspaceRequest {
  id: string;
  business_name: string;
  desired_slug: string;
  justification: string | null;
  status: WorkspaceRequestStatus;
  rejection_reason: string | null;
  created_vendor_id: string | null;
  created_at: string;
  requested_by_user_id: string;
  requester_email: string | null;
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
}

export interface Vendor {
  id: string;
  slug: string;
  business_name: string;
  is_active: boolean;
  status: VendorStatus;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface VendorDetail extends Vendor {
  member_count: number;
}

export interface Member {
  user_id: string;
  email: string;
  role: MemberRole;
  membership_id: string;
}

export interface InviteResult {
  kind: string;
  vendor_id: string;
  email: string;
  role: MemberRole;
  invitation_id: string | null;
  token: string | null;
  user_id: string | null;
  expires_at: string | null;
}

export interface PlatformUser {
  id: string;
  email: string;
  platform_role: PlatformRole;
  membership_count: number;
}

export interface VendorHealth {
  vendor_id: string;
  slug: string;
  business_name: string;
  status: string;
  is_active: boolean;
  lead_counts: {
    inquiries: number;
    callbacks: number;
    applications: number;
    cost_estimates: number;
    qr_logs: number;
    total: number;
  };
  most_recent_lead_at: string | null;
  outbox_counts: { pending: number; processing: number; sent: number; failed: number; total: number };
  oldest_pending_outbox_at: string | null;
  oldest_pending_outbox_age_seconds: number | null;
}

export interface OutboxEvent {
  id: string;
  vendor_id: string | null;
  event_type: string;
  status: string;
  attempts: number;
  max_attempts: number;
  available_at: string;
  processed_at: string | null;
  failure_reason: string | null;
}

export interface AuditLog {
  id: string;
  actor_user_id: string | null;
  actor_role: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  vendor_id: string | null;
  details: Record<string, unknown>;
  ip: string | null;
  created_at: string;
}

export interface ViewAsLead {
  id: string;
  lead_type: string;
  name: string | null;
  email: string | null;
  created_at: string;
}

export interface ViewAsLeads {
  vendor_id: string;
  leads: ViewAsLead[];
}

export interface ViewAsSiteConfig {
  vendor_id: string;
  version: number;
  config: Record<string, unknown>;
  draft_config: Record<string, unknown> | null;
  updated_at: string;
}

export interface SupportTicket {
  id: string;
  vendor_id: string | null;
  opened_by_user_id: string | null;
  assignee_user_id: string | null;
  subject: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SupportTicketMessage {
  id: string;
  ticket_id: string;
  author_user_id: string | null;
  body: string;
  is_internal: boolean;
  created_at: string;
}

export interface SupportTicketDetail extends SupportTicket {
  messages: SupportTicketMessage[];
}

// ============================================================================
// Overview
// ============================================================================

export async function getOverview(): Promise<PlatformOverview> {
  const { data } = await consoleClient.get<PlatformOverview>(`${adminBase}/overview`);
  return data;
}

// ============================================================================
// Workspace requests
// ============================================================================

export async function listWorkspaceRequests(status = 'pending'): Promise<AdminWorkspaceRequest[]> {
  const { data } = await consoleClient.get<AdminWorkspaceRequest[]>(`${adminBase}/workspace-requests`, {
    params: { status },
  });
  return data;
}

export async function approveWorkspaceRequest(id: string, slugOverride?: string): Promise<void> {
  await consoleClient.post(`${adminBase}/workspace-requests/${id}/approve`, {
    slug_override: slugOverride || undefined,
  });
}

export async function rejectWorkspaceRequest(id: string, reason?: string): Promise<void> {
  await consoleClient.post(`${adminBase}/workspace-requests/${id}/reject`, { reason: reason || undefined });
}

// ============================================================================
// Vendors
// ============================================================================

export interface VendorListParams {
  q?: string;
  status?: VendorStatus;
  include_deleted?: boolean;
}

export async function listVendors(params: VendorListParams = {}): Promise<Vendor[]> {
  const { data } = await consoleClient.get<Vendor[]>(`${adminBase}/vendors`, {
    params: {
      q: params.q || undefined,
      status: params.status || undefined,
      include_deleted: params.include_deleted || undefined,
    },
  });
  return data;
}

export async function getVendor(id: string): Promise<VendorDetail> {
  const { data } = await consoleClient.get<VendorDetail>(`${adminBase}/vendors/${id}`);
  return data;
}

export async function createVendor(body: { business_name: string; slug: string }): Promise<Vendor> {
  const { data } = await consoleClient.post<Vendor>(`${adminBase}/vendors`, body);
  return data;
}

export async function updateVendor(
  id: string,
  body: { business_name?: string; slug?: string },
): Promise<Vendor> {
  const { data } = await consoleClient.patch<Vendor>(`${adminBase}/vendors/${id}`, body);
  return data;
}

export async function suspendVendor(id: string): Promise<Vendor> {
  const { data } = await consoleClient.post<Vendor>(`${adminBase}/vendors/${id}/suspend`, {});
  return data;
}

export async function activateVendor(id: string): Promise<Vendor> {
  const { data } = await consoleClient.post<Vendor>(`${adminBase}/vendors/${id}/activate`, {});
  return data;
}

export async function deleteVendor(id: string): Promise<Vendor> {
  const { data } = await consoleClient.delete<Vendor>(`${adminBase}/vendors/${id}`);
  return data;
}

// ============================================================================
// Members
// ============================================================================

export async function listMembers(vendorId: string): Promise<Member[]> {
  const { data } = await consoleClient.get<Member[]>(`${adminBase}/vendors/${vendorId}/members`);
  return data;
}

export async function inviteMember(
  vendorId: string,
  body: { email: string; role: MemberRole },
): Promise<InviteResult> {
  const { data } = await consoleClient.post<InviteResult>(
    `${adminBase}/vendors/${vendorId}/members/invite`,
    body,
  );
  return data;
}

export async function updateMemberRole(
  vendorId: string,
  userId: string,
  role: MemberRole,
): Promise<Member> {
  const { data } = await consoleClient.patch<Member>(
    `${adminBase}/vendors/${vendorId}/members/${userId}`,
    { role },
  );
  return data;
}

export async function removeMember(vendorId: string, userId: string): Promise<void> {
  await consoleClient.delete(`${adminBase}/vendors/${vendorId}/members/${userId}`);
}

// ============================================================================
// Users / platform roles
// ============================================================================

export async function listUsers(): Promise<PlatformUser[]> {
  const { data } = await consoleClient.get<PlatformUser[]>(`${adminBase}/users`);
  return data;
}

export async function updatePlatformRole(userId: string, platformRole: PlatformRole): Promise<PlatformUser> {
  const { data } = await consoleClient.patch<PlatformUser>(
    `${adminBase}/users/${userId}/platform-role`,
    { platform_role: platformRole },
  );
  return data;
}

// ============================================================================
// Ops — health / outbox retry
// ============================================================================

export async function getVendorHealth(vendorId: string): Promise<VendorHealth> {
  const { data } = await consoleClient.get<VendorHealth>(`${adminBase}/vendors/${vendorId}/health`);
  return data;
}

export async function retryOutboxEvent(eventId: string): Promise<OutboxEvent> {
  const { data } = await consoleClient.post<OutboxEvent>(`${adminBase}/outbox/${eventId}/retry`, {});
  return data;
}

// ============================================================================
// View-as (read-only, audited)
// ============================================================================

export async function viewAsLeads(vendorId: string): Promise<ViewAsLeads> {
  const { data } = await consoleClient.get<ViewAsLeads>(`${adminBase}/vendors/${vendorId}/view-as/leads`);
  return data;
}

export async function viewAsSiteConfig(vendorId: string): Promise<ViewAsSiteConfig> {
  const { data } = await consoleClient.get<ViewAsSiteConfig>(
    `${adminBase}/vendors/${vendorId}/view-as/site-config`,
  );
  return data;
}

// ============================================================================
// Audit logs
// ============================================================================

export interface AuditLogParams {
  actor_user_id?: string;
  action?: string;
  vendor_id?: string;
  target_type?: string;
}

export async function listAuditLogs(params: AuditLogParams = {}): Promise<AuditLog[]> {
  const { data } = await consoleClient.get<AuditLog[]>(`${adminBase}/audit-logs`, {
    params: {
      actor_user_id: params.actor_user_id || undefined,
      action: params.action || undefined,
      vendor_id: params.vendor_id || undefined,
      target_type: params.target_type || undefined,
    },
  });
  return data;
}

// ============================================================================
// Support tickets
// ============================================================================

export async function listSupportTickets(): Promise<SupportTicket[]> {
  const { data } = await consoleClient.get<SupportTicket[]>(`${adminBase}/support/tickets`);
  return data;
}

export async function createSupportTicket(body: {
  subject: string;
  body: string;
  vendor_id?: string;
}): Promise<SupportTicketDetail> {
  const { data } = await consoleClient.post<SupportTicketDetail>(`${adminBase}/support/tickets`, {
    subject: body.subject,
    body: body.body,
    vendor_id: body.vendor_id || undefined,
  });
  return data;
}

export async function getSupportTicket(id: string): Promise<SupportTicketDetail> {
  const { data } = await consoleClient.get<SupportTicketDetail>(`${adminBase}/support/tickets/${id}`);
  return data;
}

export async function addSupportMessage(
  id: string,
  body: { body: string; is_internal?: boolean },
): Promise<SupportTicketDetail> {
  const { data } = await consoleClient.post<SupportTicketDetail>(
    `${adminBase}/support/tickets/${id}/messages`,
    { body: body.body, is_internal: body.is_internal ?? false },
  );
  return data;
}

export async function updateSupportTicket(
  id: string,
  body: { status?: SupportTicketStatus; assignee_user_id?: string },
): Promise<SupportTicketDetail> {
  const { data } = await consoleClient.patch<SupportTicketDetail>(
    `${adminBase}/support/tickets/${id}`,
    body,
  );
  return data;
}
