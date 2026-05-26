import axios from 'axios';
import { API_PREFIX, type SiteConfig } from './api';

export type { SiteConfig } from './api';

// Whether Clerk is configured at build time. When false, the console renders a
// "not configured" notice instead of mounting Clerk hooks — the public site is
// completely unaffected.
export const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;
export const authConfigured = Boolean(clerkPublishableKey);

const baseURL = import.meta.env.VITE_API_URL ?? '';

// Separate axios instance for authenticated console calls so public requests
// never carry an Authorization header.
const consoleClient = axios.create({ baseURL });

// A token provider is injected at runtime by <ClerkTokenBridge> (which lives
// inside <ClerkProvider> and has access to Clerk's getToken). Kept at module
// scope so the interceptor can reach it without prop-drilling.
let tokenProvider: (() => Promise<string | null>) | null = null;

export function setTokenProvider(fn: (() => Promise<string | null>) | null) {
  tokenProvider = fn;
}

consoleClient.interceptors.request.use(async (config) => {
  if (tokenProvider) {
    const token = await tokenProvider();
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ============================================================================
// Types (mirror backend app/schemas/leads.py + app/api/me.py)
// ============================================================================

export interface Membership {
  vendor_id: string;
  slug: string;
  business_name: string;
  role: 'owner' | 'agent' | 'viewer';
}

export interface Me {
  id: string;
  email: string;
  memberships: Membership[];
}

export interface Inquiry {
  id: string;
  vendor_id: string;
  name: string;
  email: string;
  message: string;
  created_at: string;
}

export interface Callback {
  id: string;
  vendor_id: string;
  name: string;
  phone: string;
  email?: string | null;
  preferred_time?: string | null;
  created_at: string;
}

export interface Application {
  id: string;
  vendor_id: string;
  name: string;
  email: string;
  phone: string;
  education?: string | null;
  course?: string | null;
  country?: string | null;
  intake?: string | null;
  message?: string | null;
  created_at: string;
}

export interface CostEstimate {
  id: string;
  vendor_id: string;
  name: string;
  email: string;
  phone: string;
  country: string;
  study_level?: string | null;
  course?: string | null;
  intake?: string | null;
  duration_months: number;
  currency?: string | null;
  est_tuition?: string | null;
  est_stay?: string | null;
  est_food?: string | null;
  est_total?: string | null;
  created_at: string;
}

export interface CostSetting {
  id: string;
  vendor_id: string;
  country: string;
  study_level: string;
  currency: string;
  tuition_per_year: string;
  rent_per_month: string;
  food_per_month: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CostSettingInput {
  country: string;
  study_level: string;
  currency: string;
  tuition_per_year: number;
  rent_per_month: number;
  food_per_month: number;
  is_active: boolean;
}

// ============================================================================
// Console API
// ============================================================================

export async function getMe(): Promise<Me> {
  const { data } = await consoleClient.get<Me>(`${API_PREFIX}/me`);
  return data;
}

const consoleBase = (vendorId: string) => `${API_PREFIX}/console/${vendorId}`;

export async function listInquiries(vendorId: string): Promise<Inquiry[]> {
  const { data } = await consoleClient.get<Inquiry[]>(`${consoleBase(vendorId)}/inquiries`);
  return data;
}

export async function listCallbacks(vendorId: string): Promise<Callback[]> {
  const { data } = await consoleClient.get<Callback[]>(`${consoleBase(vendorId)}/callbacks`);
  return data;
}

export async function listApplications(vendorId: string): Promise<Application[]> {
  const { data } = await consoleClient.get<Application[]>(`${consoleBase(vendorId)}/applications`);
  return data;
}

export async function listCostEstimates(vendorId: string): Promise<CostEstimate[]> {
  const { data } = await consoleClient.get<CostEstimate[]>(`${consoleBase(vendorId)}/cost-estimates`);
  return data;
}

export async function listCostSettings(vendorId: string): Promise<CostSetting[]> {
  const { data } = await consoleClient.get<CostSetting[]>(`${consoleBase(vendorId)}/cost-settings`);
  return data;
}

export async function createCostSetting(vendorId: string, body: CostSettingInput): Promise<CostSetting> {
  const { data } = await consoleClient.post<CostSetting>(`${consoleBase(vendorId)}/cost-settings`, body);
  return data;
}

export async function updateCostSetting(
  vendorId: string,
  settingId: string,
  body: CostSettingInput,
): Promise<CostSetting> {
  const { data } = await consoleClient.put<CostSetting>(
    `${consoleBase(vendorId)}/cost-settings/${settingId}`,
    body,
  );
  return data;
}

export async function deleteCostSetting(vendorId: string, settingId: string): Promise<void> {
  await consoleClient.delete(`${consoleBase(vendorId)}/cost-settings/${settingId}`);
}

// --- Site configuration -----------------------------------------------------

export interface SiteConfigState {
  published: SiteConfig;
  draft: SiteConfig | null;
  version: number;
  has_unpublished_changes: boolean;
}

export async function getSiteConfig(vendorId: string): Promise<SiteConfigState> {
  const { data } = await consoleClient.get<SiteConfigState>(`${consoleBase(vendorId)}/site`);
  return data;
}

export async function saveSiteDraft(vendorId: string, config: SiteConfig): Promise<SiteConfigState> {
  const { data } = await consoleClient.put<SiteConfigState>(`${consoleBase(vendorId)}/site/draft`, config);
  return data;
}

export async function publishSite(vendorId: string): Promise<SiteConfigState> {
  const { data } = await consoleClient.post<SiteConfigState>(`${consoleBase(vendorId)}/site/publish`, {});
  return data;
}
