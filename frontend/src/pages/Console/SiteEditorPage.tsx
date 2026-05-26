import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, Save, UploadCloud } from 'lucide-react';
import Button from '@/components/common/Button';
import TailwindInput from '@/components/common/TailwindInput';
import {
  getSiteConfig,
  saveSiteDraft,
  publishSite,
  getMe,
  type SiteConfig,
  type SiteConfigState,
} from '@/lib/consoleApi';
import { useConsoleContext, roleAtLeast } from './context';

const TOGGLES: { key: keyof SiteConfig['sections']; label: string }[] = [
  { key: 'show_stats', label: 'Stats band' },
  { key: 'show_cost_calculator', label: 'Cost calculator' },
  { key: 'show_callback', label: 'Callback form' },
  { key: 'show_application', label: 'Application form' },
];

export default function SiteEditorPage() {
  const { vendorId, role } = useConsoleContext();
  const qc = useQueryClient();
  const canWrite = roleAtLeast(role, 'agent');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['site', vendorId],
    queryFn: () => getSiteConfig(vendorId),
  });

  const { data: me } = useQuery({ queryKey: ['me'], queryFn: getMe });
  const slug = me?.memberships.find((m) => m.vendor_id === vendorId)?.slug;

  const { register, handleSubmit, reset, watch } = useForm<SiteConfig>();

  // Load the draft (if any) else the published config into the form.
  useEffect(() => {
    if (data) reset(data.draft ?? data.published);
  }, [data, reset]);

  const onSaved = (s: SiteConfigState) => {
    qc.setQueryData(['site', vendorId], s);
    reset(s.draft ?? s.published);
  };

  const saveM = useMutation({
    mutationFn: (c: SiteConfig) => saveSiteDraft(vendorId, c),
    onSuccess: onSaved,
  });
  const pubM = useMutation({
    mutationFn: () => publishSite(vendorId),
    onSuccess: onSaved,
  });

  const color = watch('primary_color') || '#171717';
  const pending = data?.has_unpublished_changes ?? false;

  if (isLoading) return <div className="h-64 animate-pulse rounded-xl bg-neutral-100" />;
  if (isError) return <p className="text-sm text-red-600">Failed to load site settings.</p>;

  return (
    <div className="max-w-2xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Site</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Customize your public page. Save a draft, then publish when you're happy.
          </p>
        </div>
        {slug && (
          <a
            href={`/v/${slug}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-neutral-900"
          >
            View public site <ExternalLink size={14} />
          </a>
        )}
      </div>

      {pending && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
          You have unpublished changes. They go live when you <strong>Publish</strong>.
        </div>
      )}

      <form
        className="mt-6 space-y-8"
        onSubmit={handleSubmit((c) => saveM.mutate(c))}
      >
        {/* Hero */}
        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-400">Hero</h2>
          <TailwindInput label="Headline" disabled={!canWrite} {...register('hero.headline')} />
          <TailwindInput label="Subheadline" multiline rows={3} disabled={!canWrite} {...register('hero.subheadline')} />
          <TailwindInput label="Button label" disabled={!canWrite} {...register('hero.cta_label')} />
        </section>

        {/* About */}
        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-400">About</h2>
          <TailwindInput label="About your agency" multiline rows={4} disabled={!canWrite} {...register('about')} />
        </section>

        {/* Brand */}
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-400">Brand colour</h2>
          <div className="flex items-center gap-3">
            <input
              type="color"
              disabled={!canWrite}
              className="h-10 w-14 cursor-pointer rounded border border-neutral-300 bg-white disabled:cursor-not-allowed"
              {...register('primary_color')}
            />
            <input
              type="text"
              disabled={!canWrite}
              className="w-32 rounded-lg border border-neutral-300 px-3 py-2 font-mono text-sm focus:border-blue-500 focus:outline-none disabled:bg-neutral-100"
              {...register('primary_color')}
            />
            <span
              className="rounded-md px-3 py-1.5 text-sm font-medium text-white"
              style={{ backgroundColor: color }}
            >
              Preview
            </span>
          </div>
        </section>

        {/* Sections */}
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-400">Sections shown</h2>
          <div className="grid grid-cols-2 gap-3">
            {TOGGLES.map((t) => (
              <label key={t.key} className="flex items-center gap-2 text-sm text-neutral-700">
                <input
                  type="checkbox"
                  disabled={!canWrite}
                  className="h-4 w-4 rounded border-neutral-300"
                  {...register(`sections.${t.key}` as const)}
                />
                {t.label}
              </label>
            ))}
          </div>
        </section>

        {canWrite && (
          <div className="flex items-center gap-3 border-t border-neutral-200 pt-5">
            <Button type="submit" variant="secondary" isLoading={saveM.isPending} icon={<Save size={16} />}>
              Save draft
            </Button>
            <Button
              type="button"
              onClick={() => pubM.mutate()}
              isLoading={pubM.isPending}
              disabled={!pending}
              icon={<UploadCloud size={16} />}
            >
              Publish
            </Button>
            {saveM.isError || pubM.isError ? (
              <span className="text-sm text-red-600">Something went wrong.</span>
            ) : pubM.isSuccess ? (
              <span className="text-sm text-green-600">Published — your site is live.</span>
            ) : saveM.isSuccess ? (
              <span className="text-sm text-neutral-500">Draft saved.</span>
            ) : null}
          </div>
        )}
      </form>
    </div>
  );
}
