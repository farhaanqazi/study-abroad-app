import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Pencil, Trash2, X } from 'lucide-react';
import Button from '@/components/common/Button';
import TailwindInput from '@/components/common/TailwindInput';
import {
  listCostSettings,
  createCostSetting,
  updateCostSetting,
  deleteCostSetting,
  type CostSetting,
  type CostSettingInput,
} from '@/lib/consoleApi';
import { useConsoleContext, roleAtLeast } from './context';

const schema = z.object({
  country: z.string().min(1, 'Required'),
  study_level: z.string().min(1, 'Required'),
  currency: z.string().min(1, 'Required'),
  tuition_per_year: z.coerce.number().min(0),
  rent_per_month: z.coerce.number().min(0),
  food_per_month: z.coerce.number().min(0),
  is_active: z.boolean(),
});
type FormValues = z.input<typeof schema>;

function SettingForm({
  initial,
  onSubmit,
  onCancel,
  pending,
  error,
}: {
  initial?: CostSetting;
  onSubmit: (v: CostSettingInput) => void;
  onCancel: () => void;
  pending: boolean;
  error?: string;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: initial
      ? {
          country: initial.country,
          study_level: initial.study_level,
          currency: initial.currency,
          tuition_per_year: Number(initial.tuition_per_year),
          rent_per_month: Number(initial.rent_per_month),
          food_per_month: Number(initial.food_per_month),
          is_active: initial.is_active,
        }
      : { study_level: 'any', currency: 'USD', is_active: true },
  });

  return (
    <form
      className="space-y-4"
      onSubmit={handleSubmit((v) =>
        onSubmit({
          country: v.country,
          study_level: v.study_level,
          currency: v.currency,
          tuition_per_year: Number(v.tuition_per_year),
          rent_per_month: Number(v.rent_per_month),
          food_per_month: Number(v.food_per_month),
          is_active: Boolean(v.is_active),
        }),
      )}
      noValidate
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <TailwindInput label="Country" error={errors.country?.message} {...register('country')} />
        <TailwindInput label="Study level" error={errors.study_level?.message} {...register('study_level')} />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <TailwindInput label="Currency" error={errors.currency?.message} {...register('currency')} />
        <TailwindInput label="Tuition / yr" type="number" step="0.01" error={errors.tuition_per_year?.message} {...register('tuition_per_year')} />
        <TailwindInput label="Rent / mo" type="number" step="0.01" error={errors.rent_per_month?.message} {...register('rent_per_month')} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <TailwindInput label="Food / mo" type="number" step="0.01" error={errors.food_per_month?.message} {...register('food_per_month')} />
        <label className="flex items-center gap-2 text-sm text-neutral-700">
          <input type="checkbox" className="h-4 w-4 rounded border-neutral-300" {...register('is_active')} />
          Active (shown on public site)
        </label>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button type="submit" isLoading={pending}>{initial ? 'Save changes' : 'Add setting'}</Button>
      </div>
    </form>
  );
}

export default function CostSettingsPage() {
  const { vendorId, role } = useConsoleContext();
  const qc = useQueryClient();
  const canWrite = roleAtLeast(role, 'agent');
  const [editing, setEditing] = useState<CostSetting | 'new' | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['cost-settings', vendorId],
    queryFn: () => listCostSettings(vendorId),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ['cost-settings', vendorId] });

  const createM = useMutation({
    mutationFn: (v: CostSettingInput) => createCostSetting(vendorId, v),
    onSuccess: () => { invalidate(); setEditing(null); },
  });
  const updateM = useMutation({
    mutationFn: ({ id, v }: { id: string; v: CostSettingInput }) => updateCostSetting(vendorId, id, v),
    onSuccess: () => { invalidate(); setEditing(null); },
  });
  const deleteM = useMutation({
    mutationFn: (id: string) => deleteCostSetting(vendorId, id),
    onSuccess: invalidate,
  });

  const errMsg = (e: unknown) =>
    (e as { response?: { status?: number } })?.response?.status === 409
      ? 'A setting for this country and study level already exists.'
      : 'Something went wrong. Please try again.';

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Cost settings</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Drives the public cost calculator. One row per country &amp; study level.
          </p>
        </div>
        {canWrite && (
          <Button onClick={() => setEditing('new')} icon={<Plus size={16} />}>Add setting</Button>
        )}
      </div>

      {isLoading && <div className="mt-6 h-40 animate-pulse rounded-xl bg-neutral-100" />}
      {isError && <p className="mt-6 text-sm text-red-600">Failed to load cost settings.</p>}

      {data && (
        <div className="mt-6 overflow-x-auto rounded-xl border border-neutral-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                {['Country', 'Level', 'Currency', 'Tuition/yr', 'Rent/mo', 'Food/mo', 'Active', ''].map((c) => (
                  <th key={c} className="px-4 py-3 font-medium">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {data.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-neutral-400">No cost settings yet.</td></tr>
              )}
              {data.map((s) => (
                <tr key={s.id} className="hover:bg-neutral-50">
                  <td className="px-4 py-3 font-medium text-neutral-900">{s.country}</td>
                  <td className="px-4 py-3 text-neutral-700">{s.study_level}</td>
                  <td className="px-4 py-3 text-neutral-700">{s.currency}</td>
                  <td className="px-4 py-3 text-neutral-700">{s.tuition_per_year}</td>
                  <td className="px-4 py-3 text-neutral-700">{s.rent_per_month}</td>
                  <td className="px-4 py-3 text-neutral-700">{s.food_per_month}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${s.is_active ? 'bg-green-100 text-green-700' : 'bg-neutral-100 text-neutral-500'}`}>
                      {s.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {canWrite && (
                      <div className="flex justify-end gap-1">
                        <button onClick={() => setEditing(s)} className="rounded p-1.5 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700" title="Edit">
                          <Pencil size={15} />
                        </button>
                        <button
                          onClick={() => { if (confirm(`Delete cost setting for ${s.country} / ${s.study_level}?`)) deleteM.mutate(s.id); }}
                          className="rounded p-1.5 text-neutral-400 hover:bg-red-50 hover:text-red-600"
                          title="Delete"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / edit modal */}
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-neutral-900">
                {editing === 'new' ? 'Add cost setting' : 'Edit cost setting'}
              </h2>
              <button onClick={() => setEditing(null)} className="rounded p-1 text-neutral-400 hover:bg-neutral-100">
                <X size={18} />
              </button>
            </div>
            <SettingForm
              initial={editing === 'new' ? undefined : editing}
              pending={createM.isPending || updateM.isPending}
              error={
                createM.isError ? errMsg(createM.error) : updateM.isError ? errMsg(updateM.error) : undefined
              }
              onCancel={() => setEditing(null)}
              onSubmit={(v) =>
                editing === 'new' ? createM.mutate(v) : updateM.mutate({ id: editing.id, v })
              }
            />
          </div>
        </div>
      )}
    </div>
  );
}
