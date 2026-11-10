import { notFound, redirect } from 'next/navigation';
import { cookies } from 'next/headers';
import Workspace from '../workspace';
export default async function Page({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (!['machines', 'alarms', 'incidents', 'actions', 'data'].includes(section)) notFound();
  if (section === 'data') {
    const session = (await cookies()).get('safeops_session')?.value;
    if (!session) redirect('/');
    const response = await fetch('http://127.0.0.1:8000/api/auth/me', {
      headers: { Cookie: `safeops_session=${session}` }, cache: 'no-store',
    });
    if (response.status === 401 || response.status === 403) redirect('/');
    if (!response.ok) throw new Error('Unable to verify workspace access. Please try again.');
    const user = await response.json();
    if (user.role !== 'admin') redirect('/');
  }
  return <Workspace section={section} />;
}
