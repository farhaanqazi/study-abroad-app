import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Lock, Eye } from 'lucide-react';
import {
  getVendor,
  updateVendor,
  suspendVendor,
  activateVendor,
  deleteVendor,
  listMembers,
  inviteMember,
  updateMemberRole,
  removeMember,
  getVendorHealth,
  retryOutboxEvent,
  viewAsLeads,
  viewAsSiteConfig,
  type MemberRole,
  type Member,
} from '@/lib/adminApi';
import Button from '@/components/common/Button';
import TailwindInput from '@/components/common/TailwindInput';
import TailwindSelect from '@/components/common/TailwindSelect';
import { LoadingBlock, ErrorBlock, Table, Badge, statusTone, fmtDate } from './ui';
import { useAdminContext, platformRoleAtLeast } from './context';

type Tab = 'details' | 'members' | 'health' | 'view-as';

const ROLE_OPTIONS = [
  { value: 'owner', label: 'Owner' },
  { value: 'agent', label: 'Agent' },
  { value: 'viewer', label: 'Viewer' },
];

// --------------------------------------------------------------------------- Details
function DetailsTab({ vendorId, canWrite }: { vendorId: string; canWrite: boolean }) {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({ queryKey: ['admin-vendor', vendorId], queryFn: () => getVendor(vendorId) });
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [edited, setEdited] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['admin-vendor', vendorId] });
    qc.invalidateQueries({ queryKey: ['admin-vendors'] });
  };

  const save = useMutation({
    mutationFn: () => updateVendor(vendorId, { business_name: name, slug }),
    onSuccess: () => { setEdited(false); invalidate(); },
  });
  const suspend = useMutation({ mutationFn: () => suspendVendor(vendorId), onSuccess: invalidate });
  const activate = useMutation({ mutationFn: () => activateVendor(vendorId), onSuccess: invalidate });
  const softDelete = useMutation({ mutationFn: () => deleteVendor(vendorId), onSuccess: () => { setConfirmDelete(false); invalidate(); } });

  if (isLoading) return <LoadingBlock />;
  if (isError || !data) return <ErrorBlock message="Failed to load vendor." />;

  const seed = () => {
    if (!edited) {
      setName(data.business_name);
      setSlug(data.slug);
      setEdited(true);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-neutral-200 bg-white p-5">
        <div className="mb-4 flex items-center gap-2">
          <h3 className="text-sm font-semibold text-neutral-900">Workspace</h3>
          <Badge tone={statusTone(data.status)}>{data.status}</Badge>
          <span className="text-xs text-neutral-400">{data.member_count} member(s)</span>
        </div>
        {canWrite ? (
          <div className="grid gap-3 sm:grid-cols-2" onFocus={seed}>
            <TailwindInput
              label="Business name"
              value={edited ? name : data.business_name}
              onChange={(e) => { seed(); setName(e.target.value); }}
            />
            <TailwindInput
              label="Slug"
              value={edited ? slug : data.slug}
              onChange={(e) => { seed(); setSlug(e.target.value); }}
            />
          </div>
        ) : (
          <p className="text-sm text-neutral-600">{data.business_name} · <code>/{data.slug}</code></p>
        )}
        {save.isError && <div className="mt-3"><ErrorBlock message="Save failed (slug may be taken)." /></div>}
        {canWrite && edited && (
          <div className="mt-4 flex gap-2">
            <Button size="sm" isLoading={save.isPending} onClick={() => save.mutate()}>Save changes</Button>
            <Button size="sm" variant="ghost" onClick={() => setEdited(false)}>Cancel</Button>
          </div>
        )}
      </div>

      {canWrite ? (
        <div className="rounded-xl border border-neutral-200 bg-white p-5">
          <h3 className="mb-3 text-sm font-semibold text-neutral-900">Lifecycle</h3>
          <div className="flex flex-wrap gap-2">
            {data.status !== 'suspended' && data.status !== 'deleted' && (
              <Button size="sm" variant="secondary" isLoading={suspend.isPending} onClick={() => suspend.mutate()}>
                Suspend
              </Button>
            )}
            {data.status === 'suspended' && (
              <Button size="sm" variant="secondary" isLoading={activate.isPending} onClick={() => activate.mutate()}>
                Activate
              </Button>
            )}
            {data.status !== 'deleted' && (
              confirmDelete ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-red-600">Soft-delete this workspace?</span>
                  <Button size="sm" variant="destructive" isLoading={softDelete.isPending} onClick={() => softDelete.mutate()}>
                    Confirm delete
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(false)}>Cancel</Button>
                </div>
              ) : (
                <Button size="sm" variant="destructive" onClick={() => setConfirmDelete(true)}>Soft-delete</Button>
              )
            )}
          </div>
        </div>
      ) : (
        <p className="flex items-center gap-1.5 text-xs text-neutral-400"><Lock size={12} /> Editing requires admin access.</p>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- Members
function MembersTab({ vendorId, canWrite }: { vendorId: string; canWrite: boolean }) {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({ queryKey: ['admin-members', vendorId], queryFn: () => listMembers(vendorId) });
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<MemberRole>('viewer');
  const invalidate = () => qc.invalidateQueries({ queryKey: ['admin-members', vendorId] });

  const invite = useMutation({
    mutationFn: () => inviteMember(vendorId, { email: email.trim(), role }),
    onSuccess: () => { setEmail(''); invalidate(); },
  });
  const changeRole = useMutation({
    mutationFn: ({ userId, r }: { userId: string; r: MemberRole }) => updateMemberRole(vendorId, userId, r),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (userId: string) => removeMember(vendorId, userId),
    onSuccess: invalidate,
  });

  if (isLoading) return <LoadingBlock />;
  if (isError || !data) return <ErrorBlock message="Failed to load members." />;

  const owners = data.filter((m) => m.role === 'owner');
  const isLastOwner = (m: Member) => m.role === 'owner' && owners.length <= 1;

  return (
    <div className="space-y-6">
      {canWrite && (
        <div className="rounded-xl border border-neutral-200 bg-white p-5">
          <h3 className="mb-3 text-sm font-semibold text-neutral-900">Invite member</h3>
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-64"><TailwindInput label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
            <div className="w-40">
              <TailwindSelect value={role} onChange={(e) => setRole(e.target.value as MemberRole)} options={ROLE_OPTIONS} placeholder="" />
            </div>
            <Button size="sm" isLoading={invite.isPending} disabled={!email.includes('@')} onClick={() => invite.mutate()}>
              Send invite
            </Button>
          </div>
          {invite.isError && <div className="mt-3"><ErrorBlock message="Invite failed." /></div>}
          {invite.data && (
            <p className="mt-3 text-xs text-neutral-500">
              {invite.data.kind === 'membership'
                ? 'User already existed — added directly.'
                : `Invitation created${invite.data.token ? ` (token: ${invite.data.token})` : ''}.`}
            </p>
          )}
        </div>
      )}

      <Table
        columns={['Email', 'Role', '']}
        rows={data.map((m) => [
          <span className="text-neutral-900">{m.email}</span>,
          canWrite ? (
            <select
              value={m.role}
              disabled={isLastOwner(m) || changeRole.isPending}
              onChange={(e) => changeRole.mutate({ userId: m.user_id, r: e.target.value as MemberRole })}
              className="rounded-md border border-neutral-300 bg-white px-2 py-1 text-sm disabled:bg-neutral-100 disabled:text-neutral-400"
            >
              {ROLE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          ) : (
            <Badge>{m.role}</Badge>
          ),
          canWrite ? (
            <button
              disabled={isLastOwner(m) || remove.isPending}
              onClick={() => remove.mutate(m.user_id)}
              title={isLastOwner(m) ? 'Cannot remove the last owner' : 'Remove member'}
              className="text-sm font-medium text-red-600 hover:text-red-700 disabled:cursor-not-allowed disabled:text-neutral-300"
            >
              Remove
            </button>
          ) : null,
        ])}
      />
      {(remove.isError || changeRole.isError) && <ErrorBlock message="Action failed (last-owner safety may apply)." />}
    </div>
  );
}

// --------------------------------------------------------------------------- Health
function HealthTab({ vendorId, canWrite }: { vendorId: string; canWrite: boolean }) {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({ queryKey: ['admin-health', vendorId], queryFn: () => getVendorHealth(vendorId) });
  const retry = useMutation({
    mutationFn: (eventId: string) => retryOutboxEvent(eventId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-health', vendorId] }),
  });

  if (isLoading) return <LoadingBlock />;
  if (isError || !data) return <ErrorBlock message="Failed to load health." />;

  const stat = (label: string, value: number | string) => (
    <div className="rounded-lg border border-neutral-200 bg-white p-3">
      <div className="text-xs uppercase tracking-wide text-neutral-400">{label}</div>
      <div className="mt-1 text-xl font-bold text-neutral-900">{value}</div>
    </div>
  );

  return (
    <div className="space-y-6">
      <section>
        <h3 className="mb-2 text-sm font-semibold text-neutral-900">Leads</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {stat('Inquiries', data.lead_counts.inquiries)}
          {stat('Callbacks', data.lead_counts.callbacks)}
          {stat('Applications', data.lead_counts.applications)}
          {stat('Cost est.', data.lead_counts.cost_estimates)}
          {stat('QR logs', data.lead_counts.qr_logs)}
          {stat('Total', data.lead_counts.total)}
        </div>
        <p className="mt-2 text-xs text-neutral-400">Most recent lead: {fmtDate(data.most_recent_lead_at)}</p>
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-neutral-900">Outbox</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {stat('Pending', data.outbox_counts.pending)}
          {stat('Processing', data.outbox_counts.processing)}
          {stat('Sent', data.outbox_counts.sent)}
          {stat('Failed', data.outbox_counts.failed)}
          {stat('Total', data.outbox_counts.total)}
        </div>
        <p className="mt-2 text-xs text-neutral-400">
          Oldest pending: {fmtDate(data.oldest_pending_outbox_at)}
          {data.oldest_pending_outbox_age_seconds != null && ` (${Math.round(data.oldest_pending_outbox_age_seconds)}s old)`}
        </p>
      </section>

      {data.outbox_counts.failed > 0 && (
        <section className="rounded-xl border border-amber-300 bg-amber-50 p-4">
          <p className="text-sm text-amber-800">
            {data.outbox_counts.failed} failed event(s). Retry an event by its id below.
          </p>
          {canWrite ? <OutboxRetryControl retry={retry} /> : (
            <p className="mt-2 flex items-center gap-1.5 text-xs text-amber-700"><Lock size={12} /> Retry requires admin access.</p>
          )}
        </section>
      )}
    </div>
  );
}

function OutboxRetryControl({ retry }: { retry: ReturnType<typeof useMutation<unknown, unknown, string>> }) {
  const [eventId, setEventId] = useState('');
  return (
    <div className="mt-3 flex flex-wrap items-end gap-2">
      <div className="w-80"><TailwindInput label="Outbox event id" value={eventId} onChange={(e) => setEventId(e.target.value)} /></div>
      <Button size="sm" isLoading={retry.isPending} disabled={!eventId.trim()} onClick={() => retry.mutate(eventId.trim())}>
        Retry event
      </Button>
      {retry.isError && <span className="text-xs text-red-600">Retry failed.</span>}
      {retry.isSuccess && <span className="text-xs text-green-700">Re-queued.</span>}
    </div>
  );
}

// --------------------------------------------------------------------------- View-as
function ViewAsTab({ vendorId }: { vendorId: string }) {
  const leads = useQuery({ queryKey: ['view-as-leads', vendorId], queryFn: () => viewAsLeads(vendorId) });
  const site = useQuery({ queryKey: ['view-as-site', vendorId], queryFn: () => viewAsSiteConfig(vendorId) });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm text-blue-800">
        <Eye size={16} />
        Read-only view. Every access here is <strong>audited</strong>. You cannot modify tenant data from this view.
      </div>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-neutral-900">Leads (read-only)</h3>
        {leads.isLoading && <LoadingBlock />}
        {leads.isError && <ErrorBlock message="Failed to load leads." />}
        {leads.data && (
          <Table
            columns={['Type', 'Name', 'Email', 'Created']}
            rows={leads.data.leads.map((l) => [l.lead_type, l.name ?? '—', l.email ?? '—', fmtDate(l.created_at)])}
          />
        )}
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-neutral-900">Site config (read-only)</h3>
        {site.isLoading && <LoadingBlock />}
        {site.isError && <ErrorBlock message="Failed to load site config." />}
        {site.data && (
          <div className="rounded-xl border border-neutral-200 bg-white p-4">
            <p className="mb-2 text-xs text-neutral-400">
              version {site.data.version} · updated {fmtDate(site.data.updated_at)}
              {site.data.draft_config && ' · has unpublished draft'}
            </p>
            <pre className="max-h-96 overflow-auto rounded-lg bg-neutral-50 p-3 text-xs text-neutral-700">
              {JSON.stringify(site.data.config, null, 2)}
            </pre>
          </div>
        )}
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------- Page
const TABS: { id: Tab; label: string }[] = [
  { id: 'details', label: 'Details' },
  { id: 'members', label: 'Members' },
  { id: 'health', label: 'Health' },
  { id: 'view-as', label: 'View-as' },
];

export default function VendorDetail() {
  const { vendorId = '' } = useParams();
  const { platformRole } = useAdminContext();
  const canWrite = platformRoleAtLeast(platformRole, 'admin');
  const [tab, setTab] = useState<Tab>('details');

  const { data } = useQuery({ queryKey: ['admin-vendor', vendorId], queryFn: () => getVendor(vendorId) });

  return (
    <div>
      <Link to="/admin/vendors" className="mb-3 flex items-center gap-1.5 text-xs text-neutral-400 hover:text-neutral-600">
        <ArrowLeft size={12} /> All vendors
      </Link>
      <h1 className="text-2xl font-bold text-neutral-900">{data?.business_name ?? 'Vendor'}</h1>
      {data && <p className="mt-1 text-sm text-neutral-500">/{data.slug}</p>}

      <div className="mt-6 mb-5 flex flex-wrap gap-1 border-b border-neutral-200">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition ${
              tab === t.id ? 'border-neutral-900 text-neutral-900' : 'border-transparent text-neutral-500 hover:text-neutral-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'details' && <DetailsTab vendorId={vendorId} canWrite={canWrite} />}
      {tab === 'members' && <MembersTab vendorId={vendorId} canWrite={canWrite} />}
      {tab === 'health' && <HealthTab vendorId={vendorId} canWrite={canWrite} />}
      {tab === 'view-as' && <ViewAsTab vendorId={vendorId} />}
    </div>
  );
}
