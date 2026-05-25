import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { UserButton } from '@clerk/react';
import { Building2, ChevronRight } from 'lucide-react';
import { getMe } from '@/lib/consoleApi';

export default function ConsoleHome() {
  const { data: me, isLoading, isError } = useQuery({ queryKey: ['me'], queryFn: getMe, retry: false });

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <h1 className="text-lg font-semibold text-neutral-900">Vendor Console</h1>
          <UserButton />
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-6 py-12">
        <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-400">Your workspaces</h2>

        {isLoading && <div className="mt-4 h-20 animate-pulse rounded-xl bg-neutral-100" />}

        {isError && (
          <p className="mt-4 text-sm text-red-600">
            Couldn't load your workspaces. Make sure the API is running and your sign-in is valid.
          </p>
        )}

        {me && me.memberships.length === 0 && (
          <div className="mt-4 rounded-xl border border-dashed border-neutral-300 p-10 text-center text-neutral-500">
            <Building2 className="mx-auto mb-3 h-8 w-8 text-neutral-300" />
            You're signed in as <span className="font-medium">{me.email}</span> but aren't a member of
            any workspace yet. Ask an owner to invite you.
          </div>
        )}

        {me && me.memberships.length > 0 && (
          <ul className="mt-4 space-y-2">
            {me.memberships.map((m) => (
              <li key={m.vendor_id}>
                <Link
                  to={`/console/${m.vendor_id}/leads`}
                  className="flex items-center justify-between rounded-xl border border-neutral-200 bg-white px-5 py-4 transition hover:border-neutral-300 hover:shadow-sm"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-neutral-100">
                      <Building2 size={18} className="text-neutral-500" />
                    </div>
                    <div>
                      <div className="font-medium text-neutral-900">{m.business_name}</div>
                      <div className="text-xs text-neutral-400">/{m.slug} · {m.role}</div>
                    </div>
                  </div>
                  <ChevronRight size={18} className="text-neutral-300" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
