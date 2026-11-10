'use client';

import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { api, ApiError } from './ui';

type Revalidate = () => Promise<void>;
type ResourceState = {
  updating: boolean; failure: string; authStatus: number | null;
  register: (load: Revalidate) => () => void;
  invalidate: () => Promise<void>;
  handleAuth: (error: unknown) => void;
  clearResourceError: () => void;
};
const ResourceContext = createContext<ResourceState | null>(null);

export function ResourceProvider({ children }: { children: ReactNode }) {
  const resources = useRef(new Set<Revalidate>());
  const active = useRef<Promise<void> | null>(null);
  const rerun = useRef(false);
  const [updating, setUpdating] = useState(false);
  const [failure, setFailure] = useState('');
  const [authStatus, setAuthStatus] = useState<number | null>(null);
  const register = useCallback((load: Revalidate) => {
    resources.current.add(load);
    return () => { resources.current.delete(load); };
  }, []);
  const handleAuth = useCallback((error: unknown) => {
    if (error instanceof ApiError && [401, 403].includes(error.status)) setAuthStatus(error.status);
  }, []);
  const clearResourceError = useCallback(() => { setFailure(''); setAuthStatus(null); }, []);
  const invalidate = useCallback(() => {
    if (active.current) {
      // A save that finishes during revalidation needs another read after the save.
      rerun.current = true;
      return active.current;
    }
    setUpdating(true); setFailure('');
    const operation = (async () => {
      try {
        let results: PromiseSettledResult<void>[] = [];
        do {
          rerun.current = false;
          results = await Promise.allSettled([...resources.current].map(load => load()));
        } while (rerun.current);
        const rejected = results.filter((r): r is PromiseRejectedResult => r.status === 'rejected');
        const failed = rejected.find(r => r.reason?.name !== 'AbortError');
        if (failed) {
          handleAuth(failed.reason);
          setFailure(`Unable to update displayed records. ${failed.reason instanceof Error ? failed.reason.message : 'Please try again.'} Previously loaded information has been kept where available.`);
        }
      } finally { setUpdating(false); active.current = null; }
    })();
    active.current = operation;
    return operation;
  }, [handleAuth]);
  const value = useMemo(() => ({ updating, failure, authStatus, register, invalidate, handleAuth, clearResourceError }),
    [updating, failure, authStatus, register, invalidate, handleAuth, clearResourceError]);
  return <ResourceContext.Provider value={value}>{children}</ResourceContext.Provider>;
}

export function useResources() {
  const value = useContext(ResourceContext);
  if (!value) throw new Error('ResourceProvider is required');
  return value;
}

/** One active request per resource. Cancellation + sequence checks prevent stale writes. */
export function useResource<T>(path: string | null, resetOnChange = false) {
  const { register, handleAuth } = useResources();
  const [data, setData] = useState<T | null>(null);
  const [loadedPath, setLoadedPath] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const previousPath = useRef<string | null>(null);
  const cancel = useCallback(() => { sequence.current++; controller.current?.abort(); }, []);
  const load = useCallback(async () => {
    if (!path) return;
    const revision = ++sequence.current;
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setLoading(true); setError('');
    try {
      const latest = await api(path, undefined, { signal: request.signal });
      if (request.signal.aborted) throw new DOMException('Request superseded', 'AbortError');
      if (revision === sequence.current) { setData(latest); setLoadedPath(path); }
    } catch (error) {
      if (!request.signal.aborted && revision === sequence.current) {
        setError(error instanceof Error ? error.message : 'Unable to load these records.');
        handleAuth(error);
      }
      throw error;
    } finally { if (revision === sequence.current) setLoading(false); }
  }, [path, handleAuth]);
  useEffect(() => {
    if (!path || (resetOnChange && previousPath.current !== path)) setData(null);
    previousPath.current = path;
    if (!path) { setLoading(false); setError(''); return; }
    // Errors are stored above for display; aborted requests are expected on navigation.
    void load().catch(() => {});
    return cancel;
  }, [path, load, resetOnChange, cancel]);
  useEffect(() => path ? register(load) : undefined, [path, register, load]);
  return { data: resetOnChange && loadedPath !== path ? null : data, setData, error, loading };
}
