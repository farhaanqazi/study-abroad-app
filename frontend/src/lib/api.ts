import axios from 'axios';

// In dev, point at the FastAPI server via VITE_API_URL (e.g. http://localhost:8000).
// In prod the SPA is served by FastAPI itself, so an empty baseURL → same-origin
// relative requests to /api/v1/... work.
const baseURL = import.meta.env.VITE_API_URL ?? '';

export const api = axios.create({ baseURL });

export const API_PREFIX = '/api/v1';

// ============================================================================
// Shared response shapes
// ============================================================================

export interface SubmitAck {
  ok: boolean;
  id: string;
}

export interface SiteHero {
  headline: string;
  subheadline: string;
  cta_label: string;
}

export interface SiteSections {
  show_stats: boolean;
  show_cost_calculator: boolean;
  show_application: boolean;
  show_callback: boolean;
}

export interface SiteConfig {
  hero: SiteHero;
  about: string;
  primary_color: string;
  sections: SiteSections;
}

export interface PublicConfig {
  vendor_name: string;
  vendor_slug: string;
  business_email?: string | null;
  site: SiteConfig;
}

export interface Stats {
  ok: boolean;
  students: number;
  countries: number;
  universities: number;
  experience: number;
}

export interface CostOption {
  country: string;
  study_level: string;
  currency: string;
}

export interface CostOptionsResponse {
  options: CostOption[];
}

export interface CostEstimateResult {
  ok: boolean;
  id: string;
  currency: string;
  country: string;
  study_level?: string | null;
  duration_months: number;
  tuition: string;
  stay: string;
  food: string;
  total: string;
}

// ============================================================================
// Public capture request bodies (mirror backend app/schemas/leads.py)
// ============================================================================

export interface InquiryInput {
  name: string;
  email: string;
  message: string;
}

export interface CallbackInput {
  name: string;
  phone: string;
  email?: string;
  preferred_time?: string;
}

export interface ApplicationInput {
  name: string;
  email: string;
  phone: string;
  education?: string;
  course?: string;
  country?: string;
  intake?: string;
  message?: string;
}

export interface CostEstimateInput {
  name: string;
  email: string;
  phone: string;
  country: string;
  study_level?: string;
  course?: string;
  intake?: string;
  duration_months: number;
}

// ============================================================================
// Public (vendor-by-slug) API — no auth
// ============================================================================

const publicBase = (slug: string) => `${API_PREFIX}/v/${encodeURIComponent(slug)}`;

export async function getPublicConfig(slug: string): Promise<PublicConfig> {
  const { data } = await api.get<PublicConfig>(`${publicBase(slug)}/config`);
  return data;
}

export async function getStats(slug: string): Promise<Stats> {
  const { data } = await api.get<Stats>(`${publicBase(slug)}/stats`);
  return data;
}

export async function getCostOptions(slug: string): Promise<CostOption[]> {
  const { data } = await api.get<CostOptionsResponse>(`${publicBase(slug)}/cost-options`);
  return data.options;
}

export async function submitInquiry(slug: string, body: InquiryInput): Promise<SubmitAck> {
  const { data } = await api.post<SubmitAck>(`${publicBase(slug)}/inquiries`, body);
  return data;
}

export async function submitCallback(slug: string, body: CallbackInput): Promise<SubmitAck> {
  const { data } = await api.post<SubmitAck>(`${publicBase(slug)}/callback`, body);
  return data;
}

export async function submitApplication(slug: string, body: ApplicationInput): Promise<SubmitAck> {
  const { data } = await api.post<SubmitAck>(`${publicBase(slug)}/applications`, body);
  return data;
}

export async function submitCostEstimate(
  slug: string,
  body: CostEstimateInput,
): Promise<CostEstimateResult> {
  const { data } = await api.post<CostEstimateResult>(`${publicBase(slug)}/cost-estimate`, body);
  return data;
}

export async function logQrScan(slug: string, url: string): Promise<SubmitAck> {
  const { data } = await api.post<SubmitAck>(`${publicBase(slug)}/qr/log`, { url });
  return data;
}
