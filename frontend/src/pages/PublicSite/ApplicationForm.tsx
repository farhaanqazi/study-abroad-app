import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation } from '@tanstack/react-query';
import Button from '@/components/common/Button';
import TailwindInput from '@/components/common/TailwindInput';
import { submitApplication, type ApplicationInput } from '@/lib/api';
import SuccessCard from './SuccessCard';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const schema = z.object({
  name: z.string().min(1, 'Your name is required'),
  email: z.string().min(1, 'Email is required').refine((v) => EMAIL_RE.test(v), 'Enter a valid email'),
  phone: z.string().min(3, 'A phone number is required'),
  education: z.string().optional(),
  course: z.string().optional(),
  country: z.string().optional(),
  intake: z.string().optional(),
  message: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export default function ApplicationForm({ vendorSlug }: { vendorSlug: string }) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const mutation = useMutation({
    mutationFn: (values: ApplicationInput) => submitApplication(vendorSlug, values),
    onSuccess: () => reset(),
  });

  if (mutation.isSuccess) {
    return (
      <SuccessCard
        title="Application received."
        message="Our team will review your details and contact you about next steps."
        onReset={() => mutation.reset()}
        resetLabel="Submit another"
      />
    );
  }

  return (
    <form
      className="space-y-4"
      onSubmit={handleSubmit((values) => mutation.mutate(values))}
      noValidate
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <TailwindInput label="Full name" error={errors.name?.message} {...register('name')} />
        <TailwindInput label="Phone" type="tel" error={errors.phone?.message} {...register('phone')} />
      </div>
      <TailwindInput label="Email" type="email" error={errors.email?.message} {...register('email')} />
      <div className="grid gap-4 sm:grid-cols-2">
        <TailwindInput label="Highest education (optional)" error={errors.education?.message} {...register('education')} />
        <TailwindInput label="Intended course (optional)" error={errors.course?.message} {...register('course')} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <TailwindInput label="Destination country (optional)" error={errors.country?.message} {...register('country')} />
        <TailwindInput label="Intake (optional)" placeholder="e.g. Fall 2026" error={errors.intake?.message} {...register('intake')} />
      </div>
      <TailwindInput
        label="Anything else? (optional)"
        multiline
        rows={3}
        error={errors.message?.message}
        {...register('message')}
      />
      {mutation.isError && (
        <p className="text-sm text-red-600">Something went wrong. Please try again.</p>
      )}
      <Button type="submit" isLoading={mutation.isPending}>
        Submit application
      </Button>
    </form>
  );
}
