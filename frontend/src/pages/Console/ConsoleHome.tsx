import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { UserButton } from '@clerk/react';
import { Building2, ChevronRight, ShieldCheck } from 'lucide-react';
import {
  getMe,
  createWorkspaceRequest,
  listMyWorkspaceRequests,
  type WorkspaceRequest,
} from '@/lib/consoleApi';
import Button from '@/components/common/Button';
import TailwindInput from '@/components/common/TailwindInput';

const STATUS_TONE: Record<WorkspaceRequest['status'], string> = {
  pending: 'bg-amber-100 text-amber-700',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  cancelled: 'bg-neutral-100 text-neutral-600',
};

function RequestWorkspace({ email }: { email: string }) {
  const qc = useQueryClient();
  const [businessName, setBusinessName] = useState('');
  const [desiredSlug, setDesiredSlug] = useState('');
  const [justification, setJustification] = useState('');

  const mine = useQuery({ queryKey: ['my-workspace-requests'], queryFn: listMyWorkspaceRequests, retry: false });

  const submit = useMutation({
    mutationFn: () =>
      createWorkspaceRequest({
        business_name: businessName.trim(),
        desired_slug: desiredSlug.trim(),
        justification: justification.trim() || undefined,
      }),
    onSuccess: () => {
      setBusinessName('');
      setDesiredSlug('');
      setJustification('');
      qc.invalidateQueries({ queryKey: ['my-workspace-requests'] });
    },
  });

  const pending = mine.data?.filter((r) => r.status === 'pending') ?? [];

  return (
    <div className="mt-4 space-y-5">
      <div className="rounded-xl border border-dashed border-neutral-300 p-6 text-center text-neutral-500">
        <Building2 className="mx-auto mb-3 h-8 w-8 text-neutral-300" />
        You're signed in as <span className="font-medium">{email}</span> but aren't a member of any workspace
        yet. Request one below and a platform admin will review it.
      </div>

      {mine.data && mine.data.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-neutral-400">Your requests</h3>
          <ul className="space-y-2">
            {mine.data.map((r) => (
              <li
                key={r.id}
                className="flex items-center justify-between rounded-xl border border-neutral-200 bg-white px-5 py-3"
              >
                <div>
                  <div className="font-medium text-neutral-900">{r.business_name}</div>
                  <div className="text-xs text-neutral-400">
                    /{r.desired_slug}
                    {r.status === 'rejected' && r.rejection_reason && ` · ${r.rejection_reason}`}
                  </div>
                </div>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${STATUS_TONE[r.status]}`}>
                  {r.status}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {pending.length === 0 && (
        <div className="rounded-xl border border-neutral-200 bg-white p-5">
          <h3 className="mb-3 text-sm font-semibold text-neutral-900">Request a workspace</h3>
          <div className="space-y-3">
            <TailwindInput label="Business name" value={businessName} onChange={(e) => setBusinessName(e.target.value)} />
            <TailwindInput
              label="Desired slug"
              value={desiredSlug}
              onChange={(e) => setDesiredSlug(e.target.value)}
              helperText="3–100 chars. Your public site lives at /v/<slug>."
            />
            <TailwindInput
              label="Justification (optional)"
              multiline
              rows={3}
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
            />
          </div>
          {submit.isError && (
            <p className="mt-3 text-sm text-red-600">Couldn't submit your request. The slug may already be taken.</p>
          )}
          {submit.isSuccess && <p className="mt-3 text-sm text-green-700">Request submitted — pending review.</p>}
          <div className="mt-4">
            <Button
              isLoading={submit.isPending}
              disabled={businessName.trim().length < 1 || desiredSlug.trim().length < 3}
              onClick={() => submit.mutate()}
            >
              Submit request
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function OperatorNoWorkspace() {
  // A platform operator isn't a vendor member by default — they run the
  // platform, not an agency. Point them at the back-office instead of the
  // (nonsensical-for-them) "request a workspace" form.
  return (
    <div className="mt-4 rounded-xl border border-dashed border-neutral-300 p-6 text-center text-neutral-500">
      <ShieldCheck className="mx-auto mb-3 h-8 w-8 text-neutral-300" />
      You're a platform operator and aren't a member of any vendor workspace —
      that's normal. Manage and create workspaces from the back-office.
      <div className="mt-4">
        <Link
          to="/admin"
          className="inline-flex items-center gap-1.5 rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700"
        >
          <ShieldCheck size={16} /> Go to Platform Admin
        </Link>
      </div>
    </div>
  );
}

export default function ConsoleHome() {
  const { data: me, isLoading, isError } = useQuery({ queryKey: ['me'], queryFn: getMe, retry: false });
  const isOperator = me && me.platform_role !== 'none';

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <h1 className="text-lg font-semibold text-neutral-900">Vendor Console</h1>
          <div className="flex items-center gap-3">
            {isOperator && (
              <Link
                to="/admin"
                className="flex items-center gap-1.5 rounded-lg bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-700"
              >
                <ShieldCheck size={14} /> Platform Admin
              </Link>
            )}
            <UserButton />
          </div>
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

        {me && me.memberships.length === 0 &&
          (isOperator ? <OperatorNoWorkspace /> : <RequestWorkspace email={me.email} />)}

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
