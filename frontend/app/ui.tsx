'use client';

import { ReactNode } from 'react';
export type Row = Record<string, any>;
export const fmt = (n: number) => new Intl.NumberFormat('en-IN').format(n || 0);
export const date = (s?: string) => s ? new Date(s).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—';
export const label = (s: string) => s?.replaceAll('_', ' ').toLowerCase().replace(/^./, c => c.toUpperCase());
export const shortId = (s: string) => s?.length > 35 ? s.slice(0, 12) + '…' + s.slice(-10) : s;

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); this.name = 'ApiError'; }
}

export async function api(path: string, body?: unknown, options: RequestInit = {}): Promise<any> {
  let response: Response;
  try { response = await fetch('/api' + path, { credentials: 'include', cache: 'no-store', ...options, ...(body === undefined ? {} : {
    method: 'POST', body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' },
  }) }); } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError('Unable to reach SafeOps. Check the backend connection and try again.', 0);
  }
  const value = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/login') throw new ApiError('Your session has expired. Sign in again.', 401);
    if (response.status === 403) throw new ApiError('Your role no longer has permission to access these records.', 403);
    const fields = value?.error?.fields?.map((f: Row) => `${f.loc.slice(1).join('.')}: ${f.msg}`).join('; ');
    throw new ApiError(fields || value?.error?.message || value?.detail || 'SafeOps could not complete the request. Please try again.', response.status);
  }
  if (value === null) throw new ApiError('SafeOps returned an unreadable response. Please try again.', response.status);
  return value;
}
export function Badge({ value }: { value: string }) {
  return <span className={`badge ${value?.toLowerCase()}`}><span />{label(value || 'Unknown')}</span>;
}
export function Field({ title, children }: { title: string; children: ReactNode }) {
  return <label className="field"><span>{title}</span>{children}</label>;
}
