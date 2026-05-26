import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Calculator } from 'lucide-react';
import Button from '@/components/common/Button';
import TailwindInput from '@/components/common/TailwindInput';
import TailwindSelect from '@/components/common/TailwindSelect';
import {
  getCostOptions,
  submitCostEstimate,
  type CostEstimateInput,
  type CostEstimateResult,
} from '@/lib/api';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const schema = z.object({
  country: z.string().min(1, 'Choose a destination'),
  study_level: z.string().optional(),
  duration_months: z.coerce.number().int().min(1, 'At least 1 month').max(120, 'Too long'),
  name: z.string().min(1, 'Your name is required'),
  email: z.string().min(1, 'Email is required').refine((v) => EMAIL_RE.test(v), 'Enter a valid email'),
  phone: z.string().min(3, 'A phone number is required'),
});

type FormValues = z.input<typeof schema>;

function money(currency: string, amount: string) {
  const n = Number(amount);
  return `${currency} ${Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: 0 }) : amount}`;
}

export default function CostCalculator({ vendorSlug }: { vendorSlug: string }) {
  const [result, setResult] = useState<CostEstimateResult | null>(null);

  const { data: options = [], isLoading } = useQuery({
    queryKey: ['cost-options', vendorSlug],
    queryFn: () => getCostOptions(vendorSlug),
  });

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { duration_months: 24 },
  });

  const selectedCountry = watch('country');

  const countries = useMemo(
    () => Array.from(new Set(options.map((o) => o.country))).sort(),
    [options],
  );

  const levels = useMemo(() => {
    const ls = options
      .filter((o) => o.country === selectedCountry && o.study_level && o.study_level !== 'any')
      .map((o) => o.study_level);
    return Array.from(new Set(ls)).sort();
  }, [options, selectedCountry]);

  const mutation = useMutation({
    mutationFn: (values: CostEstimateInput) => submitCostEstimate(vendorSlug, values),
    onSuccess: (data) => setResult(data),
  });

  if (isLoading) {
    return <div className="h-40 animate-pulse rounded-xl bg-neutral-100" />;
  }

  if (options.length === 0) {
    return null; // vendor has no cost data configured — hide the calculator
  }

  return (
    <div className="grid gap-8 md:grid-cols-2">
      <form
        className="space-y-4"
        onSubmit={handleSubmit((values) =>
          mutation.mutate({
            ...values,
            duration_months: Number(values.duration_months),
            study_level: values.study_level || undefined,
          }),
        )}
        noValidate
      >
        <div>
          <label className="mb-1.5 block text-sm font-medium text-neutral-700">Destination country</label>
          <TailwindSelect
            placeholder="Select a country"
            options={countries.map((c) => ({ value: c, label: c }))}
            error={errors.country?.message}
            {...register('country')}
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-neutral-700">Study level (optional)</label>
          <TailwindSelect
            placeholder="Any"
            options={levels.map((l) => ({ value: l!, label: l! }))}
            error={errors.study_level?.message}
            disabled={levels.length === 0}
            {...register('study_level')}
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-neutral-700">Duration (months)</label>
          <TailwindInput
            type="number"
            error={errors.duration_months?.message}
            {...register('duration_months')}
          />
        </div>
        <div className="border-t border-neutral-200 pt-4">
          <p className="mb-3 text-sm text-neutral-500">
            Enter your details to reveal your personalised estimate.
          </p>
          <div className="space-y-4">
            <TailwindInput label="Name" error={errors.name?.message} {...register('name')} />
            <div className="grid gap-4 sm:grid-cols-2">
              <TailwindInput label="Email" type="email" error={errors.email?.message} {...register('email')} />
              <TailwindInput label="Phone" type="tel" error={errors.phone?.message} {...register('phone')} />
            </div>
          </div>
        </div>
        {mutation.isError && (
          <p className="text-sm text-red-600">
            We couldn't estimate that combination. Try a different country.
          </p>
        )}
        <Button type="submit" isLoading={mutation.isPending} icon={<Calculator size={16} />}>
          Calculate my cost
        </Button>
      </form>

      <div className="flex items-center">
        {result ? (
          <div className="w-full rounded-2xl border border-neutral-200 bg-neutral-50 p-6">
            <p className="text-sm text-neutral-500">Estimated annual study budget</p>
            <p className="mt-1 text-4xl font-bold tracking-tight text-neutral-900">
              {money(result.currency, result.total)}
            </p>
            <p className="mt-1 text-xs text-neutral-500">
              {result.country}
              {result.study_level ? ` · ${result.study_level}` : ''} · {result.duration_months} months
            </p>
            <dl className="mt-6 space-y-3">
              {[
                ['Tuition', result.tuition],
                ['Accommodation', result.stay],
                ['Food & living', result.food],
              ].map(([label, val]) => (
                <div key={label} className="flex items-center justify-between border-b border-neutral-200 pb-2 text-sm">
                  <dt className="text-neutral-600">{label}</dt>
                  <dd className="font-medium text-neutral-900">{money(result.currency, val)}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 text-xs text-neutral-400">
              Indicative only. A counsellor will share a detailed breakdown.
            </p>
          </div>
        ) : (
          <div className="w-full rounded-2xl border border-dashed border-neutral-300 p-10 text-center text-neutral-400">
            <Calculator className="mx-auto mb-3 h-8 w-8" />
            Your estimate will appear here.
          </div>
        )}
      </div>
    </div>
  );
}
