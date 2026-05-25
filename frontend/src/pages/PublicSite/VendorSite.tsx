import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { GraduationCap, Globe2, Building2, Award } from 'lucide-react';
import { getPublicConfig, getStats } from '@/lib/api';
import InquiryForm from './InquiryForm';
import CallbackForm from './CallbackForm';
import ApplicationForm from './ApplicationForm';
import CostCalculator from './CostCalculator';

type Tab = 'inquiry' | 'callback' | 'application';

const TABS: { id: Tab; label: string }[] = [
  { id: 'inquiry', label: 'Ask a question' },
  { id: 'callback', label: 'Request a callback' },
  { id: 'application', label: 'Start an application' },
];

export default function VendorSite() {
  const { vendorSlug = '' } = useParams();
  const [tab, setTab] = useState<Tab>('inquiry');

  const { data: config, isLoading, isError } = useQuery({
    queryKey: ['public-config', vendorSlug],
    queryFn: () => getPublicConfig(vendorSlug),
    enabled: Boolean(vendorSlug),
    retry: false,
  });

  const { data: stats } = useQuery({
    queryKey: ['public-stats', vendorSlug],
    queryFn: () => getStats(vendorSlug),
    enabled: Boolean(vendorSlug) && Boolean(config),
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-40 animate-pulse rounded bg-neutral-200" />
      </div>
    );
  }

  if (isError || !config) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8 text-center">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Site not found</h1>
          <p className="mt-2 text-neutral-500">No vendor exists for &ldquo;{vendorSlug}&rdquo;.</p>
        </div>
      </div>
    );
  }

  const statItems = stats
    ? [
        { icon: GraduationCap, value: stats.students.toLocaleString(), label: 'Students guided' },
        { icon: Globe2, value: `${stats.countries}+`, label: 'Countries' },
        { icon: Building2, value: `${stats.universities}+`, label: 'Partner universities' },
        { icon: Award, value: `${stats.experience} yrs`, label: 'Experience' },
      ]
    : [];

  return (
    <main className="min-h-screen bg-white text-neutral-900">
      {/* Hero */}
      <section className="border-b border-neutral-100 bg-gradient-to-b from-neutral-50 to-white">
        <div className="mx-auto max-w-4xl px-6 py-24 text-center">
          <span className="inline-block rounded-full border border-neutral-200 bg-white px-3 py-1 text-xs font-medium text-neutral-500">
            Study Abroad Counselling
          </span>
          <h1 className="mt-5 text-4xl font-bold tracking-tight sm:text-6xl">{config.vendor_name}</h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-neutral-500">
            Your gateway to studying abroad. Tell us your goals and our counsellors will guide you
            from application to arrival.
          </p>
          <div className="mt-8 flex justify-center gap-3">
            <a
              href="#get-started"
              className="rounded-lg bg-neutral-900 px-6 py-3 text-sm font-medium text-white transition hover:bg-neutral-700"
            >
              Get started
            </a>
            <a
              href="#cost"
              className="rounded-lg border border-neutral-300 px-6 py-3 text-sm font-medium text-neutral-700 transition hover:bg-neutral-50"
            >
              Estimate my costs
            </a>
          </div>
        </div>
      </section>

      {/* Stats */}
      {statItems.length > 0 && (
        <section className="border-b border-neutral-100">
          <div className="mx-auto grid max-w-4xl grid-cols-2 gap-8 px-6 py-12 sm:grid-cols-4">
            {statItems.map(({ icon: Icon, value, label }) => (
              <div key={label} className="text-center">
                <Icon className="mx-auto mb-2 h-6 w-6 text-neutral-400" />
                <div className="text-2xl font-bold">{value}</div>
                <div className="mt-1 text-xs text-neutral-500">{label}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Cost calculator */}
      <section id="cost" className="border-b border-neutral-100 bg-neutral-50/50">
        <div className="mx-auto max-w-5xl px-6 py-20">
          <div className="mb-8 text-center">
            <h2 className="text-3xl font-semibold">What will it cost?</h2>
            <p className="mt-2 text-neutral-500">
              Get an instant, personalised estimate of tuition and living costs.
            </p>
          </div>
          <CostCalculator vendorSlug={config.vendor_slug} />
        </div>
      </section>

      {/* Contact / lead forms */}
      <section id="get-started" className="mx-auto max-w-xl px-6 py-20">
        <h2 className="mb-2 text-center text-3xl font-semibold">Get in touch</h2>
        <p className="mb-8 text-center text-neutral-500">
          However suits you best — we usually reply within a day.
        </p>

        <div className="mb-6 flex rounded-lg border border-neutral-200 bg-neutral-50 p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
                tab === t.id ? 'bg-white text-neutral-900 shadow-sm' : 'text-neutral-500 hover:text-neutral-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'inquiry' && <InquiryForm vendorSlug={config.vendor_slug} />}
        {tab === 'callback' && <CallbackForm vendorSlug={config.vendor_slug} />}
        {tab === 'application' && <ApplicationForm vendorSlug={config.vendor_slug} />}
      </section>

      {/* Footer */}
      <footer className="border-t border-neutral-100 py-10 text-center text-sm text-neutral-400">
        <p>{config.vendor_name}</p>
        {config.business_email && (
          <a href={`mailto:${config.business_email}`} className="mt-1 inline-block hover:text-neutral-600">
            {config.business_email}
          </a>
        )}
      </footer>
    </main>
  );
}
