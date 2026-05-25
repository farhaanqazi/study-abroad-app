import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getPublicConfig } from '@/lib/api';
import InquiryForm from './InquiryForm';

export default function VendorSite() {
  const { vendorSlug = '' } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['public-config', vendorSlug],
    queryFn: () => getPublicConfig(vendorSlug),
    enabled: Boolean(vendorSlug),
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-40 animate-pulse rounded bg-neutral-200" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8 text-center">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">Site not found</h1>
          <p className="mt-2 text-neutral-500">
            No vendor exists for &ldquo;{vendorSlug}&rdquo;.
          </p>
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-white text-neutral-900">
      <section className="mx-auto max-w-3xl px-6 py-20 text-center">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">{data.vendor_name}</h1>
        <p className="mx-auto mt-4 max-w-xl text-lg text-neutral-500">
          Your gateway to studying abroad. Tell us your goals and our counsellors
          will guide you from application to arrival.
        </p>
      </section>

      <section className="mx-auto max-w-xl px-6 pb-24">
        <h2 className="mb-6 text-center text-2xl font-semibold">Get in touch</h2>
        <InquiryForm vendorSlug={data.vendor_slug} />
      </section>
    </main>
  );
}
