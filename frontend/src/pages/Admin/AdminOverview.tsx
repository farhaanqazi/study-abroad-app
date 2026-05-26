import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Building2, Inbox, Users, AlertTriangle, TrendingUp } from 'lucide-react';
import { getOverview } from '@/lib/adminApi';
import { PageHeader, LoadingBlock, ErrorBlock } from './ui';

function MetricCard({
  icon,
  label,
  value,
  hint,
  to,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  hint?: string;
  to?: string;
  tone?: 'default' | 'warn';
}) {
  const body = (
    <div
      className={`rounded-xl border bg-white p-5 transition ${
        to ? 'hover:border-neutral-300 hover:shadow-sm' : ''
      } ${tone === 'warn' && Number(value) > 0 ? 'border-amber-300' : 'border-neutral-200'}`}
    >
      <div className="flex items-center gap-2 text-neutral-400">
        {icon}
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <div className="mt-2 text-3xl font-bold text-neutral-900">{value}</div>
      {hint && <div className="mt-1 text-xs text-neutral-400">{hint}</div>}
    </div>
  );
  return to ? <Link to={to}>{body}</Link> : body;
}

export default function AdminOverview() {
  const { data, isLoading, isError } = useQuery({ queryKey: ['admin-overview'], queryFn: getOverview });

  return (
    <div>
      <PageHeader title="Overview" subtitle="Platform-wide metrics across all workspaces." />

      {isLoading && <LoadingBlock />}
      {isError && <ErrorBlock message="Failed to load overview metrics." />}

      {data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <MetricCard
            icon={<Building2 size={16} />}
            label="Active vendors"
            value={data.vendors.active}
            hint={`${data.vendors.total} total · ${data.vendors.suspended} suspended · ${data.vendors.deleted} deleted`}
            to="/admin/vendors"
          />
          <MetricCard
            icon={<Inbox size={16} />}
            label="Pending requests"
            value={data.pending_workspace_requests}
            hint="Workspace requests awaiting review"
            to="/admin/requests"
            tone="warn"
          />
          <MetricCard icon={<Inbox size={16} />} label="Total leads" value={data.total_leads} hint="All lead types, all vendors" />
          <MetricCard
            icon={<AlertTriangle size={16} />}
            label="Outbox failed"
            value={data.outbox_failed}
            hint="Failed transactional-outbox events"
            tone="warn"
          />
          <MetricCard
            icon={<TrendingUp size={16} />}
            label="Recent signups"
            value={data.recent_signups_7d}
            hint="New users in the last 7 days"
          />
          <MetricCard icon={<Users size={16} />} label="Manage users" value="→" hint="Platform roles & access" to="/admin/users" />
        </div>
      )}
    </div>
  );
}
