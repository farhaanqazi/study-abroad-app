import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation } from '@tanstack/react-query';
import Button from '@/components/common/Button';
import TailwindInput from '@/components/common/TailwindInput';
import { submitCallback, type CallbackInput } from '@/lib/api';
import SuccessCard from './SuccessCard';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const schema = z.object({
  name: z.string().min(1, 'Your name is required'),
  phone: z.string().min(3, 'A phone number is required'),
  email: z
    .string()
    .optional()
    .refine((v) => !v || EMAIL_RE.test(v), 'Enter a valid email'),
  preferred_time: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export default function CallbackForm({ vendorSlug }: { vendorSlug: string }) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const mutation = useMutation({
    mutationFn: (values: CallbackInput) => submitCallback(vendorSlug, values),
    onSuccess: () => reset(),
  });

  if (mutation.isSuccess) {
    return (
      <SuccessCard
        title="We'll call you back."
        message="A counsellor will reach out at your preferred time."
        onReset={() => mutation.reset()}
      />
    );
  }

  return (
    <form
      className="space-y-4"
      onSubmit={handleSubmit((values) => mutation.mutate(values))}
      noValidate
    >
      <TailwindInput label="Name" error={errors.name?.message} {...register('name')} />
      <TailwindInput label="Phone" type="tel" error={errors.phone?.message} {...register('phone')} />
      <TailwindInput label="Email (optional)" type="email" error={errors.email?.message} {...register('email')} />
      <TailwindInput
        label="Preferred time (optional)"
        placeholder="e.g. Weekday mornings"
        error={errors.preferred_time?.message}
        {...register('preferred_time')}
      />
      {mutation.isError && (
        <p className="text-sm text-red-600">Something went wrong. Please try again.</p>
      )}
      <Button type="submit" isLoading={mutation.isPending}>
        Request a callback
      </Button>
    </form>
  );
}
