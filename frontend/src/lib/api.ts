import axios from 'axios';

// In dev, point at the FastAPI server via VITE_API_URL (e.g. http://localhost:8000).
// In prod the SPA is served by FastAPI itself, so an empty baseURL → same-origin
// relative requests to /api/v1/... work.
const baseURL = import.meta.env.VITE_API_URL ?? '';

export const api = axios.create({ baseURL });

export const API_PREFIX = '/api/v1';

// --- Public (vendor-by-slug) -------------------------------------------------

export interface PublicConfig {
  vendor_name: string;
  vendor_slug: string;
  business_email?: string | null;
}

export interface SubmitAck {
  ok: boolean;
  id: string;
}

export interface InquiryInput {
  name: string;
  email: string;
  message: string;
}

const publicBase = (slug: string) => `${API_PREFIX}/v/${encodeURIComponent(slug)}`;

export async function getPublicConfig(slug: string): Promise<PublicConfig> {
  const { data } = await api.get<PublicConfig>(`${publicBase(slug)}/config`);
  return data;
}

export async function submitInquiry(slug: string, body: InquiryInput): Promise<SubmitAck> {
  const { data } = await api.post<SubmitAck>(`${publicBase(slug)}/inquiries`, body);
  return data;
}
