import type { ReactNode } from 'react';
import { Show, SignIn } from '@clerk/react';
import { KeyRound } from 'lucide-react';
import { authConfigured } from '@/lib/consoleApi';

function NotConfigured() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-50 p-8">
      <div className="max-w-md rounded-2xl border border-neutral-200 bg-white p-8 text-center shadow-sm">
        <KeyRound className="mx-auto mb-3 h-8 w-8 text-neutral-400" />
        <h1 className="text-xl font-semibold text-neutral-900">Console not configured</h1>
        <p className="mt-2 text-sm text-neutral-500">
          The management console needs a Clerk publishable key. Set
          <code className="mx-1 rounded bg-neutral-100 px-1.5 py-0.5 text-xs">VITE_CLERK_PUBLISHABLE_KEY</code>
          in <code className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs">frontend/.env</code> and rebuild.
        </p>
        <p className="mt-4 text-xs text-neutral-400">
          The public vendor sites work without this.
        </p>
      </div>
    </div>
  );
}

function SignInScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-50 p-8">
      <div className="w-full max-w-md">
        <h1 className="mb-6 text-center text-2xl font-bold text-neutral-900">Vendor Console</h1>
        <div className="flex justify-center">
          <SignIn routing="hash" />
        </div>
      </div>
    </div>
  );
}

/** Gates the console: no Clerk key → notice; signed out → sign-in; signed in → children. */
export default function RequireAuth({ children }: { children: ReactNode }) {
  if (!authConfigured) return <NotConfigured />;
  return (
    <>
      <Show when="signed-out">
        <SignInScreen />
      </Show>
      <Show when="signed-in">{children}</Show>
    </>
  );
}
