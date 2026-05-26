import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Plus, Lock } from 'lucide-react';
import {
  listSupportTickets,
  createSupportTicket,
  getSupportTicket,
  addSupportMessage,
  updateSupportTicket,
  type SupportTicketStatus,
} from '@/lib/adminApi';
import Button from '@/components/common/Button';
import TailwindInput from '@/components/common/TailwindInput';
import { PageHeader, LoadingBlock, ErrorBlock, EmptyBlock, Table, Badge, statusTone, fmtDate } from './ui';
import { useAdminContext, platformRoleAtLeast } from './context';

const STATUS_OPTIONS: { value: SupportTicketStatus; label: string }[] = [
  { value: 'open', label: 'Open' },
  { value: 'pending', label: 'Pending' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
];

// --------------------------------------------------------------------------- Detail
function TicketDetail({ ticketId, canManage, onBack }: { ticketId: string; canManage: boolean; onBack: () => void }) {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({ queryKey: ['support-ticket', ticketId], queryFn: () => getSupportTicket(ticketId) });
  const [body, setBody] = useState('');
  const [isInternal, setIsInternal] = useState(false);
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['support-ticket', ticketId] });
    qc.invalidateQueries({ queryKey: ['support-tickets'] });
  };

  const reply = useMutation({
    mutationFn: () => addSupportMessage(ticketId, { body: body.trim(), is_internal: isInternal }),
    onSuccess: () => { setBody(''); invalidate(); },
  });
  const setStatus = useMutation({
    mutationFn: (status: SupportTicketStatus) => updateSupportTicket(ticketId, { status }),
    onSuccess: invalidate,
  });

  if (isLoading) return <LoadingBlock />;
  if (isError || !data) return <ErrorBlock message="Failed to load ticket." />;

  return (
    <div>
      <button onClick={onBack} className="mb-3 flex items-center gap-1.5 text-xs text-neutral-400 hover:text-neutral-600">
        <ArrowLeft size={12} /> All tickets
      </button>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">{data.subject}</h1>
          <p className="mt-1 text-sm text-neutral-500">
            opened {fmtDate(data.created_at)}
            {data.vendor_id && ` · vendor ${data.vendor_id}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={statusTone(data.status)}>{data.status}</Badge>
          {canManage && (
            <select
              value={data.status}
              disabled={setStatus.isPending}
              onChange={(e) => setStatus.mutate(e.target.value as SupportTicketStatus)}
              className="rounded-md border border-neutral-300 bg-white px-2 py-1 text-sm"
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      <div className="mt-6 space-y-3">
        {data.messages.map((m) => (
          <div
            key={m.id}
            className={`rounded-xl border p-4 ${m.is_internal ? 'border-amber-200 bg-amber-50' : 'border-neutral-200 bg-white'}`}
          >
            <div className="mb-1 flex items-center gap-2 text-xs text-neutral-400">
              <span className="font-mono">{m.author_user_id ?? 'system'}</span>
              <span>·</span>
              <span>{fmtDate(m.created_at)}</span>
              {m.is_internal && <Badge tone="amber">internal</Badge>}
            </div>
            <p className="whitespace-pre-wrap text-sm text-neutral-700">{m.body}</p>
          </div>
        ))}
        {data.messages.length === 0 && <EmptyBlock>No messages yet.</EmptyBlock>}
      </div>

      <div className="mt-6 rounded-xl border border-neutral-200 bg-white p-4">
        <TailwindInput label="Reply" multiline rows={3} value={body} onChange={(e) => setBody(e.target.value)} />
        <div className="mt-3 flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm text-neutral-600">
            <input type="checkbox" checked={isInternal} onChange={(e) => setIsInternal(e.target.checked)} />
            Internal note (not shown to vendor)
          </label>
          <Button size="sm" isLoading={reply.isPending} disabled={!body.trim()} onClick={() => reply.mutate()}>
            Send
          </Button>
        </div>
        {reply.isError && <div className="mt-3"><ErrorBlock message="Reply failed." /></div>}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- List
export default function SupportTickets() {
  const { platformRole } = useAdminContext();
  const canManage = platformRoleAtLeast(platformRole, 'admin');
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [vendorId, setVendorId] = useState('');

  const { data, isLoading, isError } = useQuery({ queryKey: ['support-tickets'], queryFn: listSupportTickets });

  const create = useMutation({
    mutationFn: () => createSupportTicket({ subject: subject.trim(), body: body.trim(), vendor_id: vendorId.trim() || undefined }),
    onSuccess: (t) => {
      setShowCreate(false);
      setSubject('');
      setBody('');
      setVendorId('');
      qc.invalidateQueries({ queryKey: ['support-tickets'] });
      setSelected(t.id);
    },
  });

  if (selected) {
    return <TicketDetail ticketId={selected} canManage={canManage} onBack={() => setSelected(null)} />;
  }

  return (
    <div>
      <PageHeader
        title="Support tickets"
        subtitle="Back-office tickets for troubleshooting workspaces."
        action={
          <Button icon={<Plus size={16} />} onClick={() => setShowCreate((s) => !s)}>
            New ticket
          </Button>
        }
      />

      {showCreate && (
        <div className="mb-6 rounded-xl border border-neutral-200 bg-white p-5">
          <h3 className="mb-3 text-sm font-semibold text-neutral-900">New ticket</h3>
          <div className="space-y-3">
            <TailwindInput label="Subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
            <TailwindInput label="Body" multiline rows={4} value={body} onChange={(e) => setBody(e.target.value)} />
            <TailwindInput label="Vendor id (optional)" value={vendorId} onChange={(e) => setVendorId(e.target.value)} />
          </div>
          {create.isError && <div className="mt-3"><ErrorBlock message="Create failed." /></div>}
          <div className="mt-4 flex gap-2">
            <Button size="sm" isLoading={create.isPending} disabled={!subject.trim() || !body.trim()} onClick={() => create.mutate()}>
              Create ticket
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
          </div>
        </div>
      )}

      {!canManage && (
        <p className="mb-4 flex items-center gap-1.5 text-xs text-neutral-400">
          <Lock size={12} /> Changing ticket status/assignee requires admin access.
        </p>
      )}

      {isLoading && <LoadingBlock />}
      {isError && <ErrorBlock message="Failed to load tickets." />}
      {data && data.length === 0 && <EmptyBlock>No tickets.</EmptyBlock>}

      {data && data.length > 0 && (
        <Table
          columns={['Subject', 'Status', 'Vendor', 'Updated', '']}
          rows={data.map((t) => [
            <span className="font-medium text-neutral-900">{t.subject}</span>,
            <Badge tone={statusTone(t.status)}>{t.status}</Badge>,
            t.vendor_id ? <span className="font-mono text-xs">{t.vendor_id}</span> : '—',
            fmtDate(t.updated_at),
            <button onClick={() => setSelected(t.id)} className="text-sm font-medium text-neutral-900 underline hover:text-neutral-600">
              Open
            </button>,
          ])}
        />
      )}
    </div>
  );
}
