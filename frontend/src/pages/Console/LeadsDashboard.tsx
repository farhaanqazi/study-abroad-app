import { useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import {
  listInquiries,
  listCallbacks,
  listApplications,
  listCostEstimates,
} from '@/lib/consoleApi';
import { useConsoleContext } from './context';

type Tab = 'inquiries' | 'callbacks' | 'applications' | 'cost-estimates';

const TABS: { id: Tab; label: string }[] = [
  { id: 'inquiries', label: 'Inquiries' },
  { id: 'callbacks', label: 'Callbacks' },
  { id: 'applications', label: 'Applications' },
  { id: 'cost-estimates', label: 'Cost estimates' },
];

function fmtDate(iso: string) {
  try {
    return format(new Date(iso), 'd MMM yyyy, HH:mm');
  } catch {
    return iso;
  }
}

function Table({ columns, rows }: { columns: string[]; rows: ReactNode[][] }) {
  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-neutral-300 p-12 text-center text-sm text-neutral-400">
        No records yet.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-neutral-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-4 py-3 font-medium">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {rows.map((cells, i) => (
            <tr key={i} className="hover:bg-neutral-50">
              {cells.map((cell, j) => (
                <td key={j} className="px-4 py-3 align-top text-neutral-700">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function useLeads<T>(key: Tab, vendorId: string, fn: (v: string) => Promise<T[]>, active: boolean) {
  return useQuery({ queryKey: [key, vendorId], queryFn: () => fn(vendorId), enabled: active });
}

export default function LeadsDashboard() {
  const { vendorId } = useConsoleContext();
  const [tab, setTab] = useState<Tab>('inquiries');

  const inquiries = useLeads('inquiries', vendorId, listInquiries, tab === 'inquiries');
  const callbacks = useLeads('callbacks', vendorId, listCallbacks, tab === 'callbacks');
  const applications = useLeads('applications', vendorId, listApplications, tab === 'applications');
  const estimates = useLeads('cost-estimates', vendorId, listCostEstimates, tab === 'cost-estimates');

  const active = { inquiries, callbacks, applications, 'cost-estimates': estimates }[tab];

  return (
    <div>
      <h1 className="text-2xl font-bold text-neutral-900">Leads</h1>
      <p className="mt-1 text-sm text-neutral-500">Submissions captured from your public site.</p>

      <div className="mt-6 mb-5 flex flex-wrap gap-1 border-b border-neutral-200">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition ${
              tab === t.id
                ? 'border-neutral-900 text-neutral-900'
                : 'border-transparent text-neutral-500 hover:text-neutral-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {active.isLoading && <div className="h-40 animate-pulse rounded-xl bg-neutral-100" />}
      {active.isError && <p className="text-sm text-red-600">Failed to load {tab}.</p>}

      {tab === 'inquiries' && inquiries.data && (
        <Table
          columns={['Name', 'Email', 'Message', 'Received']}
          rows={inquiries.data.map((r) => [r.name, r.email, r.message, fmtDate(r.created_at)])}
        />
      )}
      {tab === 'callbacks' && callbacks.data && (
        <Table
          columns={['Name', 'Phone', 'Email', 'Preferred time', 'Received']}
          rows={callbacks.data.map((r) => [r.name, r.phone, r.email ?? '—', r.preferred_time ?? '—', fmtDate(r.created_at)])}
        />
      )}
      {tab === 'applications' && applications.data && (
        <Table
          columns={['Name', 'Email', 'Phone', 'Course', 'Country', 'Intake', 'Received']}
          rows={applications.data.map((r) => [
            r.name, r.email, r.phone, r.course ?? '—', r.country ?? '—', r.intake ?? '—', fmtDate(r.created_at),
          ])}
        />
      )}
      {tab === 'cost-estimates' && estimates.data && (
        <Table
          columns={['Name', 'Email', 'Country', 'Level', 'Months', 'Est. total', 'Received']}
          rows={estimates.data.map((r) => [
            r.name,
            r.email,
            r.country,
            r.study_level ?? '—',
            r.duration_months,
            r.est_total != null ? `${r.currency ?? ''} ${r.est_total}` : '—',
            fmtDate(r.created_at),
          ])}
        />
      )}
    </div>
  );
}
