import { NavLink, Outlet, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { UserButton } from '@clerk/react';
import { LayoutDashboard, Inbox, Building2, Users, ScrollText, LifeBuoy, ShieldCheck } from 'lucide-react';
import { getMe } from '@/lib/consoleApi';
import type { AdminCtx } from './context';

const navItems = [
  { to: '/admin', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/admin/requests', label: 'Requests', icon: Inbox, end: false },
  { to: '/admin/vendors', label: 'Vendors', icon: Building2, end: false },
  { to: '/admin/users', label: 'Users', icon: Users, end: false },
  { to: '/admin/audit', label: 'Audit', icon: ScrollText, end: false },
  { to: '/admin/support', label: 'Support', icon: LifeBuoy, end: false },
];

const ROLE_LABEL: Record<string, string> = {
  support: 'Support',
  admin: 'Admin',
  superadmin: 'Superadmin',
};

export default function AdminLayout() {
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: getMe, retry: false });

  // RequirePlatformAdmin guarantees a non-'none' role before this renders.
  const platformRole = me?.platform_role ?? 'support';
  const ctx: AdminCtx = { me: me!, platformRole };

  return (
    <div className="flex min-h-screen bg-neutral-50">
      {/* Sidebar */}
      <aside className="flex w-60 flex-col border-r border-neutral-200 bg-white">
        <div className="border-b border-neutral-100 px-5 py-4">
          <div className="flex items-center gap-2 text-neutral-900">
            <ShieldCheck size={18} className="text-neutral-700" />
            <h2 className="text-sm font-semibold">Platform Admin</h2>
          </div>
          <span className="mt-2 inline-block rounded-full bg-neutral-900 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-white">
            {ROLE_LABEL[platformRole] ?? platformRole}
          </span>
          <div className="mt-3">
            <Link to="/console" className="text-xs text-neutral-400 hover:text-neutral-600">
              ← Back to console
            </Link>
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
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
        <div className="p-8">{me && <Outlet context={ctx} />}</div>
      </main>
    </div>
  );
}
