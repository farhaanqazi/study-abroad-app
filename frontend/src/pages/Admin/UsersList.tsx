import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Lock } from 'lucide-react';
import { listUsers, updatePlatformRole } from '@/lib/adminApi';
import type { PlatformRole } from '@/lib/consoleApi';
import { PageHeader, LoadingBlock, ErrorBlock, Table, Badge, statusTone } from './ui';
import { useAdminContext, platformRoleAtLeast } from './context';

const ROLE_OPTIONS: { value: PlatformRole; label: string }[] = [
  { value: 'none', label: 'None' },
  { value: 'support', label: 'Support' },
  { value: 'admin', label: 'Admin' },
  { value: 'superadmin', label: 'Superadmin' },
];

function roleTone(r: PlatformRole) {
  if (r === 'none') return statusTone('neutral');
  if (r === 'support') return 'blue' as const;
  return 'green' as const;
}

export default function UsersList() {
  const { me, platformRole } = useAdminContext();
  const canGrant = platformRoleAtLeast(platformRole, 'superadmin');
  const qc = useQueryClient();

  const { data, isLoading, isError } = useQuery({ queryKey: ['admin-users'], queryFn: listUsers });

  const grant = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: PlatformRole }) => updatePlatformRole(userId, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  return (
    <div>
      <PageHeader
        title="Users"
        subtitle="Platform users and their operator roles."
        action={
          !canGrant && (
            <span className="flex items-center gap-1.5 text-xs text-neutral-400">
              <Lock size={12} /> Role changes require superadmin
            </span>
          )
        }
      />

      {isLoading && <LoadingBlock />}
      {isError && <ErrorBlock message="Failed to load users." />}
      {grant.isError && <div className="mb-3"><ErrorBlock message="Role change failed." /></div>}

      {data && (
        <Table
          columns={['Email', 'Platform role', 'Workspaces', canGrant ? 'Change role' : '']}
          rows={data.map((u) => {
            const isSelf = u.id === me.id;
            return [
              <span className="text-neutral-900">
                {u.email}
                {isSelf && <span className="ml-2 text-xs text-neutral-400">(you)</span>}
              </span>,
              <Badge tone={roleTone(u.platform_role)}>{u.platform_role}</Badge>,
              u.membership_count,
              canGrant ? (
                <select
                  value={u.platform_role}
                  disabled={isSelf || grant.isPending}
                  title={isSelf ? 'You cannot change your own platform role' : 'Change platform role'}
                  onChange={(e) => grant.mutate({ userId: u.id, role: e.target.value as PlatformRole })}
                  className="rounded-md border border-neutral-300 bg-white px-2 py-1 text-sm disabled:cursor-not-allowed disabled:bg-neutral-100 disabled:text-neutral-400"
                >
                  {ROLE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              ) : null,
            ];
          })}
        />
      )}
    </div>
  );
}
