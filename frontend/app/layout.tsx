import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'SafeOps Intelligence', description: 'Industrial safety analytics and incident traceability' };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
