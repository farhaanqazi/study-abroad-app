import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, ShieldX } from 'lucide-react';
import { getMe } from '@/lib/consoleApi';
import RequireAuth from '@/pages/Console/RequireAuth';

function CenteredPanel({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-50 p-8">
      <div className="max-w-md rounded-2xl border border-neutral-200 bg-white p-8 text-center shadow-sm">
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center text-neutral-400">{icon}</div>
        <h1 className="text-xl font-semibold text-neutral-900">{title}</h1>
        <div className="mt-2 text-sm text-neutral-500">{children}</div>
      </div>
    </div>
  );
}

/**
 * Gates the /admin back-office: requires a signed-in user (via RequireAuth) whose
 * platform_role is not 'none'. Renders a clean "not authorized" panel otherwise.
 */
function AdminGate({ children }: { children: ReactNode }) {
  const { data: me, isLoading, isError } = useQuery({ queryKey: ['me'], queryFn: getMe, retry: false });

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-50">
        <div className="h-24 w-64 animate-pulse rounded-xl bg-neutral-100" />
      </div>
    );
  }

  if (isError || !me) {
    return (
      <CenteredPanel icon={<ShieldAlert className="h-9 w-9" />} title="Couldn't verify access">
        We couldn't load your account. Check that the API is reachable and your sign-in is valid.
      </CenteredPanel>
    );
  }

  if (me.platform_role === 'none') {
    return (
      <CenteredPanel icon={<ShieldX className="h-9 w-9 text-red-400" />} title="Not authorized">
        You're signed in as <span className="font-medium">{me.email}</span>, but this area is restricted to
        platform operators.{' '}
        <Link to="/console" className="text-neutral-900 underline">
          Go to your console
        </Link>
        .
      </CenteredPanel>
    );
  }

  return <>{children}</>;
}

export default function RequirePlatformAdmin({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <AdminGate>{children}</AdminGate>
    </RequireAuth>
  );
}
