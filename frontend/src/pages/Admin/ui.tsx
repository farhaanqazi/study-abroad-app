import type { ReactNode } from 'react';
import { format } from 'date-fns';

export function fmtDate(iso?: string | null) {
  if (!iso) return '—';
  try {
    return format(new Date(iso), 'd MMM yyyy, HH:mm');
  } catch {
    return iso;
  }
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold text-neutral-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-neutral-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function LoadingBlock() {
  return <div className="h-40 animate-pulse rounded-xl bg-neutral-100" />;
}

export function ErrorBlock({ message }: { message?: string }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      {message ?? 'Something went wrong. Please retry.'}
    </div>
  );
}

export function EmptyBlock({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-neutral-300 p-12 text-center text-sm text-neutral-400">
      {children}
    </div>
  );
}

export function Table({ columns, rows }: { columns: string[]; rows: ReactNode[][] }) {
  if (rows.length === 0) {
    return <EmptyBlock>No records.</EmptyBlock>;
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-neutral-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-4 py-3 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {rows.map((cells, i) => (
            <tr key={i} className="hover:bg-neutral-50">
              {cells.map((cell, j) => (
                <td key={j} className="px-4 py-3 align-top text-neutral-700">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const BADGE_TONES: Record<string, string> = {
  green: 'bg-green-100 text-green-700',
  amber: 'bg-amber-100 text-amber-700',
  red: 'bg-red-100 text-red-700',
  neutral: 'bg-neutral-100 text-neutral-600',
  blue: 'bg-blue-100 text-blue-700',
};

export function Badge({ tone = 'neutral', children }: { tone?: keyof typeof BADGE_TONES; children: ReactNode }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${BADGE_TONES[tone]}`}
    >
      {children}
    </span>
  );
}

export function statusTone(status: string): keyof typeof BADGE_TONES {
  switch (status) {
    case 'active':
    case 'sent':
    case 'approved':
    case 'resolved':
      return 'green';
    case 'pending':
    case 'processing':
    case 'suspended':
    case 'open':
      return 'amber';
    case 'failed':
    case 'rejected':
    case 'deleted':
    case 'cancelled':
    case 'closed':
      return 'red';
    default:
      return 'neutral';
  }
}
