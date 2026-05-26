import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Search } from 'lucide-react';
import { listVendors, createVendor, type VendorStatus } from '@/lib/adminApi';
import Button from '@/components/common/Button';
import TailwindInput from '@/components/common/TailwindInput';
import TailwindSelect from '@/components/common/TailwindSelect';
import { PageHeader, LoadingBlock, ErrorBlock, Table, Badge, statusTone, fmtDate } from './ui';
import { useAdminContext, platformRoleAtLeast } from './context';

export default function VendorsList() {
  const { platformRole } = useAdminContext();
  const canWrite = platformRoleAtLeast(platformRole, 'admin');
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [q, setQ] = useState('');
  const [status, setStatus] = useState<VendorStatus | ''>('');
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin-vendors', q, status, includeDeleted],
    queryFn: () =>
      listVendors({ q: q.trim() || undefined, status: status || undefined, include_deleted: includeDeleted }),
  });

  const create = useMutation({
    mutationFn: () => createVendor({ business_name: name.trim(), slug: slug.trim() }),
    onSuccess: (v) => {
      setShowCreate(false);
      setName('');
      setSlug('');
      qc.invalidateQueries({ queryKey: ['admin-vendors'] });
      navigate(`/admin/vendors/${v.id}`);
    },
  });

  return (
    <div>
      <PageHeader
        title="Vendors"
        subtitle="All workspaces on the platform."
        action={
          canWrite && (
            <Button icon={<Plus size={16} />} onClick={() => setShowCreate((s) => !s)}>
              New vendor
            </Button>
          )
        }
      />

      {showCreate && canWrite && (
        <div className="mb-6 rounded-xl border border-neutral-200 bg-white p-5">
          <h3 className="mb-3 text-sm font-semibold text-neutral-900">Create vendor</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <TailwindInput label="Business name" value={name} onChange={(e) => setName(e.target.value)} />
            <TailwindInput label="Slug" value={slug} onChange={(e) => setSlug(e.target.value)} helperText="3–100 chars, used in /v/<slug>" />
          </div>
          {create.isError && <div className="mt-3"><ErrorBlock message="Create failed. The slug may be taken or invalid." /></div>}
          <div className="mt-4 flex gap-2">
            <Button
              size="sm"
              isLoading={create.isPending}
              disabled={name.trim().length < 1 || slug.trim().length < 3}
              onClick={() => create.mutate()}
            >
              Create
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div className="relative w-64">
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search name or slug…"
            className="w-full rounded-lg border border-neutral-300 bg-white py-2 pl-9 pr-3 text-sm text-neutral-900 focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div className="w-44">
          <TailwindSelect
            placeholder="All statuses"
            value={status}
            onChange={(e) => setStatus(e.target.value as VendorStatus | '')}
            options={[
              { value: 'active', label: 'Active' },
              { value: 'suspended', label: 'Suspended' },
              { value: 'deleted', label: 'Deleted' },
            ]}
          />
        </div>
        <label className="flex items-center gap-2 pb-2.5 text-sm text-neutral-600">
          <input type="checkbox" checked={includeDeleted} onChange={(e) => setIncludeDeleted(e.target.checked)} />
          Include deleted
        </label>
      </div>

      {isLoading && <LoadingBlock />}
      {isError && <ErrorBlock message="Failed to load vendors." />}

      {data && (
        <Table
          columns={['Business', 'Slug', 'Status', 'Created', '']}
          rows={data.map((v) => [
            <span className="font-medium text-neutral-900">{v.business_name}</span>,
            <code className="text-neutral-500">/{v.slug}</code>,
            <Badge tone={statusTone(v.status)}>{v.status}</Badge>,
            fmtDate(v.created_at),
            <button
              onClick={() => navigate(`/admin/vendors/${v.id}`)}
              className="text-sm font-medium text-neutral-900 underline hover:text-neutral-600"
            >
              Open
            </button>,
          ])}
        />
      )}
    </div>
  );
}
