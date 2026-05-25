import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation } from '@tanstack/react-query';
import Button from '@/components/common/Button';
import TailwindInput from '@/components/common/TailwindInput';
import { submitInquiry, type InquiryInput } from '@/lib/api';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const schema = z.object({
  name: z.string().min(1, 'Your name is required'),
  email: z.string().min(1, 'Email is required').refine((v) => EMAIL_RE.test(v), 'Enter a valid email'),
  message: z.string().min(1, 'Tell us how we can help'),
});

type FormValues = z.infer<typeof schema>;

export default function InquiryForm({ vendorSlug }: { vendorSlug: string }) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const mutation = useMutation({
    mutationFn: (values: InquiryInput) => submitInquiry(vendorSlug, values),
    onSuccess: () => reset(),
  });

  if (mutation.isSuccess) {
    return (
      <div className="rounded-lg border border-green-200 bg-green-50 p-6 text-center">
        <p className="font-medium text-green-800">Thanks — we got your message.</p>
        <p className="mt-1 text-sm text-green-700">A counsellor will be in touch shortly.</p>
        <button
          className="mt-3 text-sm text-green-800 underline"
          onClick={() => mutation.reset()}
        >
          Send another
        </button>
      </div>
    );
  }

  return (
    <form
      className="space-y-4"
      onSubmit={handleSubmit((values) => mutation.mutate(values))}
      noValidate
    >
      <TailwindInput label="Name" error={errors.name?.message} {...register('name')} />
      <TailwindInput label="Email" type="email" error={errors.email?.message} {...register('email')} />
      <TailwindInput
        label="Message"
        multiline
        rows={4}
        error={errors.message?.message}
        {...register('message')}
      />
      {mutation.isError && (
        <p className="text-sm text-red-600">Something went wrong. Please try again.</p>
      )}
      <Button type="submit" isLoading={mutation.isPending}>
        Send inquiry
      </Button>
    </form>
  );
}
