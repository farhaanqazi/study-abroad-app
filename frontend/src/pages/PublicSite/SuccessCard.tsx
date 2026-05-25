import { CheckCircle2 } from 'lucide-react';

interface SuccessCardProps {
  title: string;
  message: string;
  onReset: () => void;
  resetLabel?: string;
}

export default function SuccessCard({ title, message, onReset, resetLabel = 'Send another' }: SuccessCardProps) {
  return (
    <div className="rounded-xl border border-green-200 bg-green-50 p-6 text-center">
      <CheckCircle2 className="mx-auto mb-2 h-8 w-8 text-green-600" />
      <p className="font-medium text-green-800">{title}</p>
      <p className="mt-1 text-sm text-green-700">{message}</p>
      <button className="mt-3 text-sm font-medium text-green-800 underline" onClick={onReset}>
        {resetLabel}
      </button>
    </div>
  );
}
