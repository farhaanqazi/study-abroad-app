import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Lock } from 'lucide-react';
import {
  listWorkspaceRequests,
  approveWorkspaceRequest,
  rejectWorkspaceRequest,
  type AdminWorkspaceRequest,
} from '@/lib/adminApi';
import Button from '@/components/common/Button';
import TailwindInput from '@/components/common/TailwindInput';
import { PageHeader, LoadingBlock, ErrorBlock, EmptyBlock, Badge, fmtDate } from './ui';
import { useAdminContext, platformRoleAtLeast } from './context';

function RequestCard({ req, canReview }: { req: AdminWorkspaceRequest; canReview: boolean }) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<null | 'approve' | 'reject'>(null);
  const [slugOverride, setSlugOverride] = useState('');
  const [reason, setReason] = useState('');

  const refetch = () => qc.invalidateQueries({ queryKey: ['admin-workspace-requests'] });

  const approve = useMutation({
    mutationFn: () => approveWorkspaceRequest(req.id, slugOverride.trim() || undefined),
    onSuccess: () => {
      setMode(null);
      refetch();
    },
  });
  const reject = useMutation({
    mutationFn: () => rejectWorkspaceRequest(req.id, reason.trim() || undefined),
    onSuccess: () => {
      setMode(null);
      refetch();
    },
  });

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-neutral-900">{req.business_name}</h3>
            <Badge tone="amber">{req.status}</Badge>
          </div>
          <p className="mt-0.5 text-xs text-neutral-400">
            requested slug <code className="rounded bg-neutral-100 px-1">/{req.desired_slug}</code> ·{' '}
            {req.requester_email ?? req.requested_by_user_id} · {fmtDate(req.created_at)}
          </p>
          {req.justification && <p className="mt-2 text-sm text-neutral-600">{req.justification}</p>}
        </div>
      </div>

      {canReview ? (
        <div className="mt-4 border-t border-neutral-100 pt-4">
          {mode === null && (
            <div className="flex gap-2">
              <Button size="sm" variant="primary" onClick={() => setMode('approve')}>
                Approve
              </Button>
              <Button size="sm" variant="destructive" onClick={() => setMode('reject')}>
                Reject
              </Button>
            </div>
          )}

          {mode === 'approve' && (
            <div className="space-y-3">
              <TailwindInput
                label="Slug override (optional)"
                value={slugOverride}
                onChange={(e) => setSlugOverride(e.target.value)}
                helperText={`Leave blank to use /${req.desired_slug}`}
              />
              {approve.isError && <ErrorBlock message="Approve failed. The slug may already be taken." />}
              <div className="flex gap-2">
                <Button size="sm" isLoading={approve.isPending} onClick={() => approve.mutate()}>
                  Confirm approve
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setMode(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {mode === 'reject' && (
            <div className="space-y-3">
              <TailwindInput
                label="Reason (optional)"
                multiline
                rows={2}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
              {reject.isError && <ErrorBlock message="Reject failed. Please retry." />}
              <div className="flex gap-2">
                <Button size="sm" variant="destructive" isLoading={reject.isPending} onClick={() => reject.mutate()}>
                  Confirm reject
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setMode(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <p className="mt-4 flex items-center gap-1.5 border-t border-neutral-100 pt-4 text-xs text-neutral-400">
          <Lock size={12} /> Approving and rejecting requires admin access.
        </p>
      )}
    </div>
  );
}

export default function WorkspaceRequestsQueue() {
  const { platformRole } = useAdminContext();
  const canReview = platformRoleAtLeast(platformRole, 'admin');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin-workspace-requests'],
    queryFn: () => listWorkspaceRequests('pending'),
  });

  return (
    <div>
      <PageHeader title="Workspace requests" subtitle="Pending requests from users to provision a workspace." />

      {isLoading && <LoadingBlock />}
      {isError && <ErrorBlock message="Failed to load workspace requests." />}
      {data && data.length === 0 && <EmptyBlock>No pending requests.</EmptyBlock>}

      {data && data.length > 0 && (
        <div className="space-y-3">
          {data.map((req) => (
            <RequestCard key={req.id} req={req} canReview={canReview} />
          ))}
        </div>
      )}
    </div>
  );
}
