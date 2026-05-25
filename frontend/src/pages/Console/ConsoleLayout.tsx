import { NavLink, Outlet, useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { UserButton } from '@clerk/react';
import { Inbox, Settings, ArrowLeft } from 'lucide-react';
import { getMe } from '@/lib/consoleApi';

const navItems = [
  { to: 'leads', label: 'Leads', icon: Inbox },
  { to: 'cost-settings', label: 'Cost settings', icon: Settings },
];

export default function ConsoleLayout() {
  const { vendorId = '' } = useParams();

  const { data: me, isLoading, isError } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
    retry: false,
  });

  const membership = me?.memberships.find((m) => m.vendor_id === vendorId);

  return (
    <div className="flex min-h-screen bg-neutral-50">
      {/* Sidebar */}
      <aside className="flex w-60 flex-col border-r border-neutral-200 bg-white">
        <div className="border-b border-neutral-100 px-5 py-4">
          <Link to="/console" className="flex items-center gap-1.5 text-xs text-neutral-400 hover:text-neutral-600">
            <ArrowLeft size={12} /> All workspaces
          </Link>
          <h2 className="mt-2 truncate text-sm font-semibold text-neutral-900">
            {membership?.business_name ?? 'Console'}
          </h2>
          {membership && (
            <span className="mt-1 inline-block rounded-full bg-neutral-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-neutral-500">
              {membership.role}
            </span>
          )}
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive ? 'bg-neutral-900 text-white' : 'text-neutral-600 hover:bg-neutral-100'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-neutral-100 p-4">
          <div className="flex items-center gap-2">
            <UserButton />
            <span className="truncate text-xs text-neutral-500">{me?.email}</span>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        {isLoading && <div className="p-8 text-sm text-neutral-400">Loading…</div>}
        {isError && (
          <div className="p-8 text-sm text-red-600">
            Couldn't load your account. Check that the API is reachable and your token is valid.
          </div>
        )}
        {!isLoading && !isError && !membership && (
          <div className="p-8">
            <h1 className="text-lg font-semibold text-neutral-900">No access</h1>
            <p className="mt-1 text-sm text-neutral-500">
              You don't have a membership for this workspace.{' '}
              <Link to="/console" className="text-neutral-900 underline">Pick another</Link>.
            </p>
          </div>
        )}
        {membership && (
          <div className="p-8">
            <Outlet context={{ vendorId, role: membership.role }} />
          </div>
        )}
      </main>
    </div>
  );
}
