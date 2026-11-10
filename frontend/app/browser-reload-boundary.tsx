'use client';

import { ReactNode, useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { api, ApiError } from './ui';

declare global {
  interface Window { __safeopsNavigationHandled?: boolean }
}

/** Process a genuine document reload once; client navigation never replays the reset. */
export default function BrowserReloadBoundary({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [phase, setPhase] = useState<'checking' | 'redirecting' | 'ready'>('checking');

  useEffect(() => {
    if (window.__safeopsNavigationHandled) { setPhase('ready'); return; }
    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
    if (navigation?.type !== 'reload') {
      window.__safeopsNavigationHandled = true;
      setPhase('ready');
      return;
    }
    // This is the only persisted temporary selection used by this application.
    // Session cookies and unrelated browser storage are deliberately untouched.
    localStorage.removeItem('safeops-workspace');
    let cancelled = false;
    async function decide() {
      let authenticated = false;
      try { await api('/auth/me'); authenticated = true; }
      catch (error) {
        // Let the existing sign-in/data-loading flow report an unavailable backend.
        // A confirmed anonymous user retains the normal login flow for their URL.
        if (!(error instanceof ApiError && error.status === 401)) authenticated = true;
      }
      if (cancelled) return;
      window.__safeopsNavigationHandled = true;
      if (authenticated && window.location.pathname !== '/') {
        setPhase('redirecting');
        router.replace('/', { scroll: true });
      } else {
        // On Overview the route is already correct; clear its transient URL
        // state synchronously before mounting children. Next integrates this
        // native history call with its router, without an extra page request.
        if (authenticated && (window.location.search || window.location.hash)) {
          window.history.replaceState(window.history.state, '', '/');
        }
        setPhase('ready');
      }
    }
    void decide();
    return () => { cancelled = true; };
  }, [router]);

  useEffect(() => {
    if (phase === 'redirecting' && pathname === '/') setPhase('ready');
  }, [phase, pathname]);

  if (phase !== 'ready') return <main className="initial"><p>Opening workspace…</p></main>;
  return children;
}
