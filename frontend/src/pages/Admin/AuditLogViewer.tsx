import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listAuditLogs, type AuditLogParams } from '@/lib/adminApi';
import Button from '@/components/common/Button';
import { PageHeader, LoadingBlock, ErrorBlock, Table, fmtDate } from './ui';

export default function AuditLogViewer() {
  const [draft, setDraft] = useState<AuditLogParams>({});
  const [applied, setApplied] = useState<AuditLogParams>({});

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ['admin-audit', applied],
    queryFn: () => listAuditLogs(applied),
  });

  const field = (key: keyof AuditLogParams, placeholder: string) => (
    <input
      value={draft[key] ?? ''}
      onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
      placeholder={placeholder}
      className="w-48 rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 focus:border-blue-500 focus:outline-none"
    />
  );

  return (
    <div>
      <PageHeader title="Audit log" subtitle="Append-only record of platform-operator actions." />

      <div className="mb-5 flex flex-wrap items-center gap-2">
        {field('action', 'Action prefix…')}
        {field('actor_user_id', 'Actor user id…')}
        {field('vendor_id', 'Vendor id…')}
        {field('target_type', 'Target type…')}
        <Button size="sm" isLoading={isFetching} onClick={() => setApplied({ ...draft })}>
          Apply filters
        </Button>
        <Button size="sm" variant="ghost" onClick={() => { setDraft({}); setApplied({}); }}>
          Clear
        </Button>
      </div>

      {isLoading && <LoadingBlock />}
      {isError && <ErrorBlock message="Failed to load audit logs." />}

      {data && (
        <Table
          columns={['When', 'Actor', 'Role', 'Action', 'Target', 'Vendor', 'IP']}
          rows={data.map((l) => [
            fmtDate(l.created_at),
            <span className="font-mono text-xs">{l.actor_user_id ?? '—'}</span>,
            l.actor_role ?? '—',
            <code className="text-neutral-900">{l.action}</code>,
            l.target_type ? <span className="font-mono text-xs">{l.target_type}:{l.target_id ?? '?'}</span> : '—',
            <span className="font-mono text-xs">{l.vendor_id ?? '—'}</span>,
            l.ip ?? '—',
          ])}
        />
      )}
    </div>
  );
}
