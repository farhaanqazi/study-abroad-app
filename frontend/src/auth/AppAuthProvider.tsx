import { useEffect, type ReactNode } from 'react';
import { ClerkProvider, useAuth } from '@clerk/react';
import { authConfigured, clerkPublishableKey, setTokenProvider } from '@/lib/consoleApi';

/**
 * Bridges Clerk's getToken into the console axios interceptor. Renders nothing;
 * must live inside <ClerkProvider>.
 */
function TokenBridge() {
  const { getToken } = useAuth();
  useEffect(() => {
    setTokenProvider(() => getToken());
    return () => setTokenProvider(null);
  }, [getToken]);
  return null;
}

/**
 * Wraps the app in Clerk auth ONLY when a publishable key is configured. With no
 * key, children render unchanged (Clerk is never mounted), so the public site
 * works and the console routes show a "not configured" notice instead.
 *
 * The key comes from VITE_CLERK_PUBLISHABLE_KEY; @clerk/react@6 requires it as a
 * typed prop, so it's passed from the env value (never hardcoded).
 */
export default function AppAuthProvider({ children }: { children: ReactNode }) {
  if (!authConfigured) return <>{children}</>;
  return (
    <ClerkProvider
      publishableKey={clerkPublishableKey!}
      afterSignOutUrl="/console"
      // After any sign-in/sign-up (incl. the Google OAuth round-trip), land on
      // the console instead of bouncing back to the bland home page at "/".
      signInForceRedirectUrl="/console"
      signUpForceRedirectUrl="/console"
    >
      <TokenBridge />
      {children}
    </ClerkProvider>
  );
}
