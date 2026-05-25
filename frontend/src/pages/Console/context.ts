import { useOutletContext } from 'react-router-dom';

export interface ConsoleCtx {
  vendorId: string;
  role: 'owner' | 'agent' | 'viewer';
}

export const useConsoleContext = () => useOutletContext<ConsoleCtx>();

/** owner > agent > viewer. */
export function roleAtLeast(role: ConsoleCtx['role'], min: ConsoleCtx['role']): boolean {
  const rank = { owner: 3, agent: 2, viewer: 1 } as const;
  return rank[role] >= rank[min];
}
