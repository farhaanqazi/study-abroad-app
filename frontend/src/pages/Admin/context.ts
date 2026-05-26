import { useOutletContext } from 'react-router-dom';
import type { Me, PlatformRole } from '@/lib/consoleApi';

export interface AdminCtx {
  me: Me;
  platformRole: PlatformRole;
}

export const useAdminContext = () => useOutletContext<AdminCtx>();

/** none < support < admin < superadmin. A higher tier satisfies a lower one. */
const RANK: Record<PlatformRole, number> = { none: 0, support: 1, admin: 2, superadmin: 3 };

export function platformRoleAtLeast(role: PlatformRole, min: PlatformRole): boolean {
  return RANK[role] >= RANK[min];
}
