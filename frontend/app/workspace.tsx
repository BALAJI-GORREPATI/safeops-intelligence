'use client';

import { useCallback, useEffect, useRef, useState, FormEvent, ReactNode } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import DataPage from './data-page';
import BrowserReloadBoundary from './browser-reload-boundary';
import { api, ApiError, Badge, Field, Row, fmt, date, label, shortId } from './ui';
import { ResourceProvider, useResources, useResource } from './resources';
import { Activity, ArrowRight, Bell, Check, CheckCheck, ChevronLeft, ChevronRight, CircleHelp,
  Database, Factory, Gauge, LayoutDashboard, LogOut, Menu, Plus, Search, ShieldCheck, TriangleAlert, Wrench, X } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Pie, PieChart, Cell } from 'recharts';

const navigation = [
  ['dashboard', 'Overview', LayoutDashboard], ['machines', 'Machines', Factory], ['alarms', 'Alarms', Bell],
  ['incidents', 'Incidents', TriangleAlert], ['actions', 'Corrective actions', Wrench], ['data', 'Data & validation', Database],
] as const;
const headings: Record<string, [string, string]> = {
  dashboard: ['Safety overview', 'A clear view of operational risk, from signal to resolution.'],
  machines: ['Machines', 'Inspect equipment, protective systems and operating history.'],
  alarms: ['Alarm workbench', 'Prioritize signals and preserve every operator response.'],
  incidents: ['Incident investigations', 'Follow the evidence. Understand what happened and why.'],
  actions: ['Corrective actions', 'Turn investigation findings into verified improvements.'],
  data: ['Data & validation', 'Generate trusted datasets, review findings and verify results.'],
};
const colors = ['#DC3545', '#EA580C', '#D97706', '#426783'];
const emptyRows: Row[] = [];
function Empty({ children }: { children: ReactNode }) { return <div className="empty"><ShieldCheck size={30} /><h3>No records to show</h3><p>{children}</p></div>; }
export default function Workspace({ section }: { section: string }) {
  // Search params are read client-side to keep dashboard links shareable.
  return <BrowserReloadBoundary><ResourceProvider><WorkspaceInner section={section} /></ResourceProvider></BrowserReloadBoundary>;
}

function WorkspaceInner({ section }: { section: string }) {
  const router = useRouter();
  const { updating, invalidate, failure: updateFailure, authStatus, clearResourceError } = useResources();
  const [user, setUser] = useState<Row | null>(null);
  const [booting, setBooting] = useState(true);
  const [workspace, setWorkspace] = useState('manual');
  const [plant, setPlant] = useState('');
  const [period, setPeriod] = useState('all');
  const [start, setStart] = useState('2026-10-01');
  const [end, setEnd] = useState('2026-10-31');
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [mobileNav, setMobileNav] = useState(false);
  const [detail, setDetail] = useState<{ type: string; id: string } | null>(null);
  const [modal, setModal] = useState<Row | null>(null);
  const notify = useCallback((message: string) => { setToast(message); void invalidate(); }, [invalidate]);
  const directory = useResource<Row[]>(user ? user.role === 'admin' ? '/datasets' : '/workspaces' : null);
  const operators = useResource<Row[]>(user ? '/users' : null);
  const locations = useResource<Row[]>(user ? `/plants?workspace=${workspace}` : null);
  const runs = directory.data || emptyRows;
  const people = operators.data || emptyRows;
  const plants = locations.data || emptyRows;
  const resourceError = directory.error || operators.error || locations.error;
  useEffect(() => { if (toast) { const timer = setTimeout(() => setToast(''), 5000); return () => clearTimeout(timer); } }, [toast]);

  useEffect(() => {
    api('/auth/me').then(u => { setUser(u); setWorkspace(localStorage.getItem('safeops-workspace') || 'manual'); })
      .catch(error => { if (!(error instanceof ApiError && error.status === 401)) setError(error.message); }).finally(() => setBooting(false));
  }, []);
  useEffect(() => {
    if (!user) return;
    localStorage.setItem('safeops-workspace', workspace);
  }, [workspace, user]);
  useEffect(() => {
    const running = runs.some(r => ['QUEUED', 'RUNNING'].includes(r.status));
    if (running && !updating) { const timer = setTimeout(() => { void invalidate(); }, 2000); return () => clearTimeout(timer); }
  }, [runs, updating, invalidate]);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('detail')) setDetail({ type: section, id: params.get('detail')! });
  }, [section]);

  useEffect(() => {
    if (!booting && section === 'data' && (!user || user.role !== 'admin')) router.replace('/');
  }, [booting, section, user, router]);

  useEffect(() => {
    if (authStatus === 401) { setUser(null); setDetail(null); setModal(null); }
    if (authStatus === 403) {
      let cancelled = false;
      api('/auth/me').then(current => {
        if (cancelled) return;
        setUser(current); setDetail(null); setModal(null); clearResourceError();
        setError('Your access has changed. Only records permitted for your role are available.');
        if (section === 'data' && current.role !== 'admin') router.replace('/');
      }).catch(error => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) setUser(null);
        else setError(error.message);
      });
      return () => { cancelled = true; };
    }
  }, [authStatus, clearResourceError, router, section]);

  const query = new URLSearchParams({ workspace });
  if (plant) query.set('plant_id', plant);
  if (period === 'custom') {
    if (start) query.set('start', new Date(start+'T00:00:00').toISOString());
    if (end) { const exclusiveEnd = new Date(end+'T00:00:00'); exclusiveEnd.setDate(exclusiveEnd.getDate()+1); query.set('end', exclusiveEnd.toISOString()); }
  }
  const open = (type: string, id: string) => setDetail({ type, id });
  const canEdit = user && ['admin', 'engineer'].includes(user.role);

  if (booting) return <main className="initial"><ShieldCheck size={32} /><p>Connecting to SafeOps…</p></main>;
  if (section === 'data' && (!user || user.role !== 'admin')) return null;
  if (!user) return <Login notice={authStatus === 401 ? 'Your session has expired. Sign in again.' : error} onLogin={u => { clearResourceError(); setError(''); setUser(u); setWorkspace(localStorage.getItem('safeops-workspace') || 'manual'); }} />;
  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? 'visible' : ''}`}>
      <Link href="/" className="brand"><span className="brand-icon"><ShieldCheck size={23} /></span><span>SafeOps<small>INTELLIGENCE</small></span></Link>
      <div className="workspace-label">OPERATIONS WORKSPACE</div>
      <nav aria-label="Primary">{navigation.filter(([key]) => key !== 'data' || user.role === 'admin').map(([key, title, Icon]) => <Link key={key} className={section === key ? 'active' : ''} href={key === 'dashboard' ? '/' : '/'+key} onClick={() => setMobileNav(false)}><Icon size={18} />{title}{key === 'data' && <span className="nav-dot" />}</Link>)}</nav>
      <div className="sidebar-bottom"><div className="safety-note"><ShieldCheck size={18} /><div>Evidence before decisions<small>Every safety event has a history.</small></div></div><div className="profile"><span className="avatar">{user.name[0]}</span><div>{user.name}<small>{label(user.role)}</small></div><button className="icon-button" aria-label="Sign out" onClick={() => api('/auth/logout', {}).then(() => setUser(null)).catch(e => setError(e.message))}><LogOut size={16} /></button></div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><button className="icon-button mobile-menu" aria-label="Toggle navigation" onClick={() => setMobileNav(v => !v)}><Menu size={20} /></button><div className="breadcrumb">Workspace <ChevronRight size={13} /><strong>{headings[section][0]}</strong></div></header>
      <main id="main-content"><div className="page-heading"><div><div className="eyebrow">SAFEOPS / {section === 'dashboard' ? 'OPERATIONS' : section.toUpperCase()}</div><h1>{headings[section][0]}</h1><p>{headings[section][1]}</p></div>{((section === 'machines' && user.role === 'admin') || (section === 'actions' && canEdit)) && <div className="heading-actions">{section === 'machines' && user.role === 'admin' && <><button className="button secondary" onClick={() => setModal({ kind: 'config', resource: 'plants' })}><Plus size={16} />Add plant</button><button className="button" onClick={() => setModal({ kind: 'config', resource: 'machines' })}><Plus size={16} />Add machine</button></>}{section === 'actions' && canEdit && <button className="button" onClick={() => setModal({ kind: 'action' })}><Plus size={16} />New action</button>}</div>}</div>
        {(error || resourceError) && <div role="alert" className="alert error"><TriangleAlert size={18} />{error || resourceError}<button className="icon-button" aria-label="Dismiss error" onClick={() => setError('')}><X size={16} /></button></div>}
        {updateFailure && <div className="alert error" role="alert">{updateFailure}</div>}
        {section !== 'data' && <div className="scopebar"><Field title="Dataset"><select aria-label="Dataset" value={workspace} onChange={e => { setWorkspace(e.target.value); setPlant(''); }}><option value="manual">Manual operations</option>{runs.filter(r => r.status === 'COMPLETED').map(r => <option key={r.id} value={r.id}>{label(r.config.preset)} · {fmt(r.config.events)} alarms · seed {r.config.seed}</option>)}</select></Field><Field title="Plant"><select aria-label="Plant" value={plant} onChange={e => setPlant(e.target.value)}><option value="">All plants</option>{plants.map(p => <option value={p.id} key={p.id}>{p.name}</option>)}</select></Field>{['dashboard', 'alarms'].includes(section) && <><Field title="Period"><select aria-label="Period" value={period} onChange={e => setPeriod(e.target.value)}><option value="all">All recorded activity</option><option value="custom">Custom date range</option></select></Field>{period === 'custom' && <><Field title="From"><input aria-label="Start date" type="date" value={start} onChange={e => setStart(e.target.value)} /></Field><Field title="Through"><input aria-label="End date" type="date" value={end} min={start} onChange={e => setEnd(e.target.value)} /></Field></>}</>}</div>}
        {section === 'dashboard' ? <Dashboard admin={user.role === 'admin'} query={query.toString()} open={open} /> : section === 'data' ? <DataPage runs={runs} workspace={workspace} role={user.role} notify={notify} select={id => { setWorkspace(id); setPlant(''); }} /> : <Records section={section} query={query.toString()} open={open} />}
        <footer><span><ShieldCheck size={13} />SafeOps Intelligence</span><span>Safety records · complete history</span></footer>
      </main>
    </div>
    {toast && <div className="toast" role="status"><CheckCheck size={18} />{toast}</div>}
    {detail && <Detail detail={detail} user={user} people={people} close={() => setDetail(null)} open={open} notify={notify} showModal={setModal} />}
    {modal && <ModalForm modal={modal} workspace={workspace} plants={plants} people={people} close={() => setModal(null)} notify={notify} />}
  </div>;
}

function Login({ onLogin, notice }: { onLogin: (u: Row) => void; notice?: string }) {
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try { await api('/auth/login', Object.fromEntries(form)); onLogin(await api('/auth/me')); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <main className="login-page"><div className="login-story"><div className="brand"><span className="brand-icon"><ShieldCheck /></span><span>SafeOps<small>INTELLIGENCE</small></span></div><div><div className="eyebrow">INDUSTRIAL SAFETY, CONNECTED.</div><h1>Every signal.<br />A safer decision.</h1><p>Connect machine events to investigations and verified corrective actions. Keep the full story in view.</p><div className="login-principles"><span><Activity />Evidence history</span><span><ShieldCheck />Traceable decisions</span><span><CheckCheck />Verified outcomes</span></div></div><small>Built for the people behind safe operations.</small></div><div className="login-form"><div className="eyebrow">LOCAL DEMONSTRATION</div><h2>Enter your workspace</h2><p>Choose a role to explore its operational workflows.</p><form onSubmit={submit}>{notice && <div className="alert info" role="alert">{notice}</div>}<Field title="Working role"><select name="role" defaultValue="admin"><option value="operator">Plant operator</option><option value="engineer">Maintenance engineer</option><option value="planner">Production planner · read only</option><option value="admin">OT / IT administrator</option></select></Field><Field title="Demo password"><input name="password" type="password" autoComplete="current-password" required placeholder="Password from your local setup" /></Field>{error && <div role="alert" className="alert error">{error}</div>}<button className="button" disabled={busy}>{busy ? 'Connecting…' : 'Open workspace'}<ArrowRight size={17} /></button></form><p className="demo-disclosure"><CircleHelp size={16} />Local demo authentication. Configure a production identity provider before external use.</p></div></main>;
}

function Dashboard({ query, open, admin }: { admin: boolean; query: string; open: (type: string, id: string) => void }) {
  const { data, error } = useResource<Row>('/dashboard?'+query, true);
  if (!data) return error ? <div role="alert" className="alert error">{error}</div> : <div className="loading">Calculating safety indicators…</div>;
  const kpis = [['Physical alarms', data.total_alarms, Bell, 'Distinct source events', '/alarms'], ['Critical alarms', data.critical_alarms, TriangleAlert, 'Highest priority signals', '/alarms?severity=CRITICAL'], ['Open incidents', data.open_incidents, Activity, 'Awaiting verified resolution', '/incidents?status=ACTIVE'], ['Delayed responses', data.delayed_acknowledgements, Gauge, 'Late or still overdue', '/alarms?status=DELAYED']] as const;
  return <>{error && <div role="alert" className="alert error">{error}</div>}<div className="section-caption">OPERATIONAL SNAPSHOT<span>Derived from stored safety records</span></div><div className="kpis">{kpis.map(([title, value, Icon, hint, href], i) => <Link href={href} className={`kpi kpi-${i}`} key={title}><div><span>{title}</span><Icon size={18} /></div><strong>{fmt(value)}</strong><small>{hint}<ArrowRight size={14} /></small></Link>)}</div>
    <div className="chart-grid"><section className="panel"><div className="panel-heading"><div><h2>Alarm activity</h2><p>Distinct physical events, grouped by UTC day</p></div><span className="chart-legend"><i />Alarms</span></div>{data.trends.length ? <div className="chart"><ResponsiveContainer width="100%" height={240}><AreaChart data={data.trends} margin={{ top: 10, right: 12, left: -24, bottom: 0 }}><CartesianGrid strokeDasharray="3 4" vertical={false} stroke="#e8edf1" /><XAxis dataKey="date" tickFormatter={d => new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })} axisLine={false} tickLine={false} tick={{ fill: '#7c8b9a', fontSize: 11 }} minTickGap={36} /><YAxis axisLine={false} tickLine={false} tick={{ fill: '#7c8b9a', fontSize: 11 }} /><Tooltip contentStyle={{ borderRadius: 6, border: '1px solid #e2e8f0' }} /><Area isAnimationActive={false} type="monotone" dataKey="alarms" stroke="#087f8c" fill="#087f8c" fillOpacity={0.08} strokeWidth={2} /></AreaChart></ResponsiveContainer></div> : <Empty>Select an activity set to inspect recorded alarm history.</Empty>}<div className="chart-foot">{fmt(data.ingested_records)} ingested records · {fmt(data.ingested_records-data.total_alarms)} source replays excluded<details className="plant-rates"><summary>Plant alarm rates · {data.rate_period_days} days</summary>{data.by_plant.map((p: Row) => <div key={p.name}><span>{p.name}</span><strong>{p.alarms_per_day} / day</strong></div>)}</details></div></section>
    <section className="panel severity-panel"><div className="panel-heading"><div><h2>Severity profile</h2><p>Focus attention where it matters</p></div></div>{data.total_alarms ? <div className="donut"><ResponsiveContainer width="100%" height={155}><PieChart><Pie isAnimationActive={false} data={data.severity} dataKey="value" innerRadius={51} outerRadius={69} paddingAngle={3} stroke="none">{colors.map(c => <Cell key={c} fill={c} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer><div className="donut-label"><strong>{fmt(data.total_alarms)}</strong><small>total alarms</small></div></div> : <div className="zero-chart">No alarms recorded</div>}<div className="severity-list">{data.severity.map((s: Row, i: number) => <Link href={'/alarms?severity='+s.name} key={s.name}><span><i style={{ background: colors[i] }} />{label(s.name)}</span><strong>{fmt(s.value)}</strong><small>{data.total_alarms ? Math.round(s.value/data.total_alarms*100) : 0}%</small></Link>)}</div></section></div>
    <div className="secondary-grid"><section className="panel"><div className="panel-heading"><div><h2>Priority investigations</h2><p>Open incidents requiring engineering attention</p></div><Link className="text-link" href="/incidents?status=ACTIVE">View all<ArrowRight size={14} /></Link></div>{data.priority_incidents.length ? <div className="incident-list">{data.priority_incidents.map((i: Row) => <button key={i.id} onClick={() => open('incidents', i.id)}><span className={`severity-bar ${i.severity.toLowerCase()}`} /><div><strong>{i.title}</strong><small>{date(i.occurred_at)} · {label(i.status)}</small></div><Badge value={i.severity} /><ChevronRight size={16} /></button>)}</div> : <Empty>No open investigations in this scope.</Empty>}</section><section className="panel"><div className="panel-heading"><div><h2>Machines to watch</h2><p>Highest physical alarm volume</p></div><Factory size={18} /></div><div className="machine-ranking">{data.top_machines.map((m: Row, i: number) => <button key={m.id} onClick={() => open('machines', m.id)}><span className="rank">0{i+1}</span><div><strong>{m.name}</strong><span className="track"><i style={{ width: `${m.alarms/data.top_machines[0].alarms*100}%` }} /></span></div><strong>{fmt(m.alarms)}</strong><ChevronRight size={14} /></button>)}{!data.top_machines.length && <Empty>No machine alarms in this scope.</Empty>}</div></section></div>
    <div className="metric-strip">{[['Median response', `${Math.round(data.median_ack_seconds)}s`, '/alarms'], ['Critical on time', `${data.critical_on_time_percentage.toFixed(1)}%`, '/alarms?severity=CRITICAL'], ['Overdue actions', fmt(data.overdue_actions), '/actions?status=OVERDUE'], ['Verified actions', `${data.verification_percentage.toFixed(1)}%`, '/actions?status=VERIFIED'], ['Flood episodes', fmt(data.floods), '/alarms'], ['Nuisance patterns', fmt(data.nuisance_patterns), '/alarms']].map(([title, value, href]) => <Link href={href} key={title}><span>{title}</span><strong>{value}</strong><ArrowRight size={13} /></Link>)}</div>
    <section className="panel recurrence"><div className="panel-heading"><div><h2>Recurring & unsafe conditions</h2><p>Rule-based findings · recurrence rate {data.recurrence_rate.toFixed(1)}% · last analysis {date(data.rule_analysis_at)}</p></div><Link href={admin ? "/data" : "/incidents"} className="text-link">{admin ? "Inspect rules" : "Investigate"}<ArrowRight size={14} /></Link></div>{data.recurring.length ? data.recurring.map((d: Row, i: number) => <div className="finding" key={i}><TriangleAlert size={17} /><div><strong>{label(d.rule_id)}</strong><p>{d.explanation}</p><small>{date(d.occurred_at)} · {shortId(d.target_record_id)}</small></div><Badge value={d.severity} /></div>) : <p className="panel-padding muted">No recurring or unsafe conditions in the latest analysis for this scope.</p>}</section>
  </>;
}

function Records({ section, query, open }: { section: string; query: string; open: (type: string, id: string) => void }) {
  const [search, setSearch] = useState(''); const [severity, setSeverity] = useState(''); const [status, setStatus] = useState('');
  const [machine, setMachine] = useState('');
  const { data: machineOptions } = useResource<Row>(section === 'alarms' ? '/machines?'+query+'&limit=100' : null);
  const machines: Row[] = machineOptions?.items || [];
  const [debouncedSearch, setDebouncedSearch] = useState('');
  useEffect(() => { const timer = setTimeout(() => setDebouncedSearch(search), 200); return () => clearTimeout(timer); }, [search]);
  const [page, setPage] = useState(1);
  useEffect(() => { const p = new URLSearchParams(window.location.search); setSeverity(p.get('severity') || ''); setStatus(p.get('status') || ''); setMachine(p.get('machine_id') || ''); }, [section]);
  useEffect(() => { setPage(1); }, [search, severity, status, query, machine]);
  const params = new URLSearchParams(query); params.set('page', String(page)); params.set('q', debouncedSearch);
  if (severity) params.set('severity', severity);
  if (status) params.set('status', status);
  if (machine) params.set('machine_id', machine);
  const { data, error, loading: busy } = useResource<Row>('/'+section+'?'+params);
  const statuses: Record<string, string[]> = { alarms: ['UNACKNOWLEDGED', 'ACKNOWLEDGED', 'DELAYED', 'LATE', 'INVALID'], incidents: ['ACTIVE', ...['OPEN', 'INVESTIGATING', 'ACTION_PENDING', 'RESOLVED', 'CLOSED']], actions: ['OVERDUE', 'OPEN', 'IN_PROGRESS', 'COMPLETED', 'VERIFIED', 'CLOSED'] };
  return <section className="panel records-panel"><div className="table-toolbar"><div className="searchbox"><Search size={16} /><input aria-label="Search records" placeholder={section === 'machines' ? 'Search machines or IDs…' : 'Search records…'} value={search} onChange={e => setSearch(e.target.value)} /></div>{section !== 'machines' && <select aria-label="Severity filter" value={severity} onChange={e => setSeverity(e.target.value)}><option value="">All severities</option>{['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(s => <option key={s}>{s}</option>)}</select>}{statuses[section] && <select aria-label="Status filter" value={status} onChange={e => setStatus(e.target.value)}><option value="">All statuses</option>{statuses[section].map(s => <option key={s} value={s}>{label(s)}</option>)}</select>}{section === 'alarms' && <select aria-label="Machine filter" value={machine} onChange={e => setMachine(e.target.value)}><option value="">All machines</option>{machines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select>}<span className="record-count">{data ? fmt(data.total) : '…'} records</span></div>
    {error && <div role="alert" className="alert error">{error}</div>}
    <div className={`table-scroll ${busy ? 'updating' : ''}`} aria-busy={busy}><table><thead><tr>{(section === 'machines' ? ['Equipment', 'Plant', 'Type', 'Current state', ''] : section === 'alarms' ? ['Alarm / source', 'Machine', 'Severity', 'Occurred', 'Response', ''] : section === 'incidents' ? ['Investigation', 'Machine', 'Severity', 'Status', 'Occurred', ''] : ['Corrective action', 'Responsible engineer', 'Priority', 'Status', 'Due', '']).map((c, i) => <th key={i}>{c}</th>)}</tr></thead><tbody>{data?.items.map((r: Row) => <tr key={r.id}>
      {section === 'machines' ? <><td><button className="record-title" onClick={() => open(section, r.id)}><span className="equipment-icon"><Factory size={17} /></span><span>{r.name}<small title={r.id}>{shortId(r.id)}</small></span></button></td><td>{r.plant_name}</td><td>{r.kind}</td><td><Badge value={r.current_state} /></td></> : section === 'alarms' ? <><td><button className="record-title" onClick={() => open(section, r.id)}><span>{r.message}<small title={r.id}>{shortId(r.id)}{r.is_replay && <span className="inline-warning"> · SOURCE REPLAY</span>}{r.in_flood && <span className="inline-warning"> · ALARM FLOOD</span>}{r.is_nuisance && <span className="cell-note"> · NUISANCE PATTERN</span>}</small></span></button></td><td>{r.machine_name}</td><td><Badge value={r.severity} /></td><td className="nowrap">{date(r.occurred_at)}</td><td><Badge value={r.status} /><small className="cell-note">{r.delay_seconds === null ? (r.overdue ? 'Response overdue' : 'Awaiting operator') : `${Math.round(r.delay_seconds)}s response`}</small></td></> : section === 'incidents' ? <><td><button className="record-title" onClick={() => open(section, r.id)}><span>{r.title}<small title={r.id}>{shortId(r.id)}{r.missing_context && <span className="inline-warning"> · MISSING CONTEXT</span>}</small></span></button></td><td>{r.machine_name}</td><td><Badge value={r.severity} /></td><td><Badge value={r.status} /></td><td className="nowrap">{date(r.occurred_at)}</td></> : <><td><button className="record-title" onClick={() => open(section, r.id)}><span>{r.description}<small title={r.incident_id}>{shortId(r.incident_id)}</small></span></button></td><td>{r.assignee_name}</td><td><Badge value={r.priority} /></td><td><Badge value={r.status} />{r.unverified_closure && <small className="inline-warning">Verification missing</small>}</td><td className="nowrap">{date(r.due_at)}{r.overdue && <small className="inline-warning">Overdue</small>}</td></>}
      <td><button className="icon-button" aria-label={'Open '+(r.name || r.message || r.title || 'action')} onClick={() => open(section, r.id)}><ChevronRight size={17} /></button></td>
    </tr>)}</tbody></table></div>{!data ? <div className="loading">Loading records…</div> : !data.items.length ? <Empty>Adjust the filters or add an operational record.</Empty> : null}
    <div className="pagination"><span>{data?.total ? `${(page-1)*25+1}–${Math.min(page*25, data.total)} of ${fmt(data.total)}` : '0 records'}<small>25 per page</small></span><div><button className="button secondary" disabled={page <= 1 || busy} onClick={() => setPage(p => p-1)}><ChevronLeft size={14} />Previous</button><button className="button secondary" disabled={!data || page*25 >= data.total || busy} onClick={() => setPage(p => p+1)}>Next<ChevronRight size={14} /></button></div></div>
  </section>;
}

function Dialog({ title, close, children, wide = false }: { title: string; close: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const element = ref.current;
    element?.focus();
    function key(e: KeyboardEvent) {
      if (e.key === 'Escape') { e.stopImmediatePropagation(); close(); }
      if (e.key === 'Tab') {
        const focusable = element?.querySelectorAll<HTMLElement>('button:not(:disabled), a, input, select, textarea, [tabindex="0"]');
        if (!focusable?.length) return;
        const first = focusable[0], last = focusable[focusable.length-1];
        if (e.shiftKey && (document.activeElement === first || document.activeElement === element)) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('keydown', key); previous?.focus(); };
  }, [close]);
  return <div className="overlay" onMouseDown={e => { if (e.target === e.currentTarget) close(); }}><div ref={ref} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} className={wide ? 'detail-drawer' : 'modal'}><div className="dialog-heading"><div><div className="eyebrow">SAFETY RECORD</div><h2>{title}</h2></div><button className="icon-button" aria-label="Close dialog" onClick={close}><X size={21} /></button></div>{children}</div></div>;
}

function Detail({ detail, user, people, close, open, notify, showModal }: { detail: { type: string; id: string }; user: Row; people: Row[]; close: () => void; open: (type: string, id: string) => void; notify: (s: string) => void; showModal: (m: Row) => void }) {
  const { data, error: loadError } = useResource<Row>(`/${detail.type}/${detail.id}`, true);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [tab, setTab] = useState('evidence');
  useEffect(() => { setError(''); }, [detail.type, detail.id]);
  const canEdit = ['admin', 'engineer'].includes(user.role);
  async function submit(event: FormEvent<HTMLFormElement>, path: string) {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(event.currentTarget));
    if (!window.confirm('Save this change to the safety record and its permanent history?')) return;
    setBusy(true); setError('');
    try { await api(path, body); notify('Saved. The safety history has been updated.'); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  const type = detail.type;
  const current = data?.[type === 'machines' ? 'machine' : type === 'alarms' ? 'alarm' : type === 'incidents' ? 'incident' : 'action'];
  const nextIncident = current && ['OPEN', 'INVESTIGATING', 'ACTION_PENDING', 'RESOLVED', 'CLOSED'][['OPEN', 'INVESTIGATING', 'ACTION_PENDING', 'RESOLVED', 'CLOSED'].indexOf(current.status)+1];
  const nextAction = current && ['OPEN', 'IN_PROGRESS', 'COMPLETED', 'VERIFIED', 'CLOSED'][['OPEN', 'IN_PROGRESS', 'COMPLETED', 'VERIFIED', 'CLOSED'].indexOf(current.status)+1];
  return <Dialog title={type === 'machines' ? 'Equipment detail' : type === 'alarms' ? 'Alarm investigation' : type === 'incidents' ? 'Incident traceability' : 'Action & verification'} close={close} wide>
    {(error || loadError) && <div className="alert error" role="alert">{error || loadError}</div>}{!data ? <div className="loading">Loading evidence…</div> : <div className="detail-body"><div className="record-summary"><div className="record-id">{current.id}</div><h3>{current.name || current.message || current.title || current.description}</h3><div className="summary-meta">{(current.severity || current.priority) && <Badge value={current.severity || current.priority} />}{current.status && <Badge value={current.status} />}<span>{date(current.occurred_at || current.due_at || current.created_at)}</span></div></div>
      {type === 'machines' && <><div className="detail-section"><h3>Protective systems</h3><div className="detail-meta"><span>Plant<strong>{data.plant.name}</strong></span><span>Operating state<strong>{data.states[0]?.state || 'Unknown'}</strong></span></div>{data.interlocks.map((l: Row) => <div className="subrecord" key={l.id}><ShieldCheck size={18} /><div><strong>{l.name}</strong><small>Guard {l.guard_state} · {l.mandatory ? 'Mandatory' : 'Optional'} · effective {date(l.effective_from)}{l.effective_to ? ' through '+date(l.effective_to) : ''}</small></div><Badge value={l.state} />{user.role === 'admin' && !l.effective_to && <button className="text-link" onClick={() => showModal({ kind: 'config', resource: 'interlocks', initial: l })}>Revise</button>}</div>)}{data.zones.map((z: Row) => <div className="subrecord" key={z.id}><div><strong>{z.name}</strong><small>{z.restriction}</small></div>{user.role === 'admin' && !z.effective_to && <button className="text-link" onClick={() => showModal({ kind: 'config', resource: 'zones', initial: { ...z, machine_id: current.id } })}>Revise</button>}</div>)}</div>
      {user.role === 'admin' && <div className="button-row">{['plants', 'zones', 'interlocks', 'definitions'].map(resource => <button className="button secondary" key={resource} onClick={() => showModal({ kind: 'config', resource, machine_id: current.id, plant_id: current.plant_id })}><Plus size={14} />{label(resource)}</button>)}</div>}
      <div className="detail-section"><h3>Alarm definitions</h3>{data.definitions.map((d: Row) => <div className="subrecord" key={d.id}><div><strong>{d.name}</strong><small>{d.source} · respond within {d.ack_deadline_seconds}s{d.effective_to && ' · superseded'}</small></div><Badge value={d.severity} />{user.role === 'admin' && !d.effective_to && <button className="text-link" onClick={() => showModal({ kind: 'config', resource: 'definitions', initial: d })}>Revise</button>}</div>)}</div>
      {canEdit && <details className="detail-section"><summary>Record a machine-state change</summary><form onSubmit={e => submit(e, `/machines/${current.id}/state`)}><div className="form-grid"><Field title="Machine state"><select name="state">{['STOPPED', 'RUNNING', 'MAINTENANCE', 'FAULT'].map(s => <option key={s}>{s}</option>)}</select></Field><Field title="Interlock"><select name="interlock_state">{['ENGAGED', 'RELEASED', 'BYPASSED', 'FAILED'].map(s => <option key={s}>{s}</option>)}</select></Field><Field title="Guard"><select name="guard_state"><option>CLOSED</option><option>OPEN</option></select></Field><Field title="Reason"><input name="reason" required minLength={5} maxLength={240} /></Field></div><button className="button" disabled={busy}>Save state event</button></form></details>}
      <div className="detail-section"><h3>Recent alarms</h3>{data.alarms.map((a: Row) => <button className="subrecord clickable" key={a.id} onClick={() => open('alarms', a.id)}><div><strong>{a.message}</strong><small>{date(a.occurred_at)}</small></div><Badge value={a.severity} /><ChevronRight size={15} /></button>)}</div><div className="detail-section"><h3>Related incidents</h3>{data.incidents.map((i: Row) => <button className="subrecord clickable" key={i.id} onClick={() => open('incidents', i.id)}><div><strong>{i.title}</strong><small>{label(i.status)}</small></div><ChevronRight size={15} /></button>)}</div><div className="detail-section"><h3>State-transition timeline</h3><p className="muted">Latest 100 events. Historical events remain authoritative.</p><div className="timeline">{data.states.map((s: Row) => <div key={s.id}><i /><small>{date(s.occurred_at)}</small><strong>{label(s.state)}</strong><p>{s.reason}</p></div>)}</div></div></>}
      {type === 'alarms' && <><div className="detail-section"><h3>Signal context</h3><div className="detail-meta"><span>Machine<button className="text-link" onClick={() => open('machines', data.machine.id)}>{data.machine.name}<ArrowRight size={13} /></button></span><span>Definition<strong>{data.definition.name}</strong></span><span>Occurred<strong>{date(current.occurred_at)}</strong></span><span>Ingested<strong>{date(current.created_at)}</strong></span><span>Source event<strong className="mono">{current.source_event_id}</strong></span><span>Response deadline<strong>{data.definition.ack_deadline_seconds}s · {data.definition.source}</strong></span><span>Machine at event<strong>{data.state.state}</strong></span><span>Operator shift<strong>{date(data.shift.starts_at)} — {date(data.shift.ends_at)}</strong></span></div>{data.source_records.length > 1 && <div className="alert warning"><TriangleAlert size={17} />{data.source_records.length} ingestions share this source event. Replays are excluded from physical alarm counts.</div>}{data.interlock_states.map((l: Row) => <div className="subrecord" key={l.id}><span>Guard <strong>{l.guard_state}</strong></span><Badge value={l.state} /></div>)}{data.zones.map((z: Row) => <p key={z.id} className="muted">{z.name} · {z.restriction}</p>)}</div>
      <div className="detail-section"><h3>Operator response</h3>{data.acknowledgement ? <div className="evidence-box"><strong>{data.acknowledgement.user_name}</strong><p>{data.acknowledgement.note}</p><small>{date(data.acknowledgement.acknowledged_at)} · {current.delay_seconds}s after occurrence</small></div> : user.role !== 'planner' ? <form onSubmit={e => submit(e, `/alarms/${current.id}/acknowledge`)}><p className="muted">Your identity and the current response time will be recorded permanently.</p><Field title="Operator note"><textarea name="note" required minLength={5} maxLength={2000} placeholder="What did you check at the machine?" /></Field><button className="button" disabled={busy}><CheckCheck size={16} />Acknowledge alarm</button></form> : <p className="muted">Awaiting acknowledgement by an operator or engineer.</p>}</div><div className="detail-section"><h3>Linked investigations</h3>{data.incidents.map((i: Row) => <button className="subrecord clickable" key={i.id} onClick={() => open('incidents', i.id)}><strong>{i.title}</strong><ChevronRight size={15} /></button>)}{canEdit && <button className="button secondary" onClick={() => showModal({ kind: 'incident', alarm_id: current.id })}><Plus size={15} />Open investigation from this alarm</button>}</div></>}
      {type === 'incidents' && <>{data.missing_context && <div className="alert warning"><TriangleAlert size={18} />Triggering evidence is missing. This incident cannot progress until evidence is attached.</div>}<div className="tabs"><button className={tab === 'evidence' ? 'active' : ''} onClick={() => setTab('evidence')}>Evidence chain</button><button className={tab === 'timeline' ? 'active' : ''} onClick={() => setTab('timeline')}>Chronological timeline</button></div>{tab === 'timeline' ? <div className="timeline">{data.timeline.map((e: Row) => <div key={e.id}><i /><small>{date(e.occurred_at)}</small><strong>{e.kind}</strong><p>{e.description}</p></div>)}</div> : <><div className="detail-section"><h3>Machine & triggering evidence</h3><button className="subrecord clickable" onClick={() => open('machines', data.machine.id)}><Factory size={18} /><strong>{data.machine.name}</strong><ChevronRight size={16} /></button>{data.alarm_details.map((a: Row) => <div className="evidence-box" key={a.alarm.id}><button className="text-link" onClick={() => open('alarms', a.alarm.id)}>{a.alarm.message}<ArrowRight size={15} /></button><p>{date(a.alarm.occurred_at)} · {a.state.state} · {a.definition.source}</p><small>Zone: {a.zones.map((z: Row) => z.name).join(', ') || 'No zone context'} · {a.acknowledgement ? 'Acknowledged by '+a.acknowledgement.user_name : 'Unacknowledged'}</small></div>)}{canEdit && <details><summary>Attach triggering alarm evidence</summary><form onSubmit={e => submit(e, `/incidents/${current.id}/evidence`)}><Field title="Alarm ID (same machine)"><input name="alarm_id" required maxLength={160} /></Field><button className="button secondary" disabled={busy}>Attach evidence</button></form></details>}</div><div className="detail-section"><div className="inline-heading"><h3>Corrective actions</h3>{canEdit && !['CLOSED', 'RESOLVED'].includes(current.status) && <button className="text-link" onClick={() => showModal({ kind: 'action', incident_id: current.id })}><Plus size={14} />Create action</button>}</div>{data.actions.length ? data.actions.map((a: Row) => <button className="subrecord clickable" key={a.id} onClick={() => open('actions', a.id)}><div><strong>{a.description}</strong><small>{a.verification_evidence || 'Verification pending'}</small></div><Badge value={a.status} /><ChevronRight size={15} /></button>) : <p className="muted">No corrective actions assigned.</p>}</div></>}{canEdit && nextIncident && <div className="detail-section"><h3>Progress investigation</h3><p className="muted">Next stage: {label(nextIncident)}. Resolution requires all actions verified.</p><form onSubmit={e => submit(e, `/incidents/${current.id}/transition`)}><input type="hidden" name="status" value={nextIncident} /><Field title="Investigation note"><textarea name="note" minLength={5} maxLength={2000} required /></Field><button disabled={busy} className="button">Move to {label(nextIncident)}<ArrowRight size={15} /></button></form></div>}</>}
      {type === 'actions' && <><div className="detail-section"><h3>Ownership & evidence</h3><div className="detail-meta"><span>Responsible engineer<strong>{current.assignee_name}</strong></span><span>Due<strong>{date(current.due_at)}</strong></span><span>Completed<strong>{date(current.completed_at)}</strong></span><span>Verified<strong>{date(current.verified_at)}</strong></span></div><button className="subrecord clickable" onClick={() => open('incidents', data.incident.id)}><div><strong>{data.incident.title}</strong><small>Open complete incident trace</small></div><ChevronRight size={16} /></button>{current.verification_evidence && <div className="evidence-box"><strong>Verification evidence</strong><p>{current.verification_evidence}</p><small>Verifier: {current.verified_by}</small></div>}{current.status === 'CLOSED' && !current.verification_evidence && <div className="alert warning">Imported closure lacks verification. Preserved as an anomaly.</div>}</div>
      {canEdit && !['CLOSED', 'VERIFIED'].includes(current.status) && <details className="detail-section"><summary>Reassign engineer</summary><form onSubmit={e => submit(e, `/actions/${current.id}/assign`)}><Field title="Responsible engineer"><select name="assignee_id" defaultValue={current.assignee_id}>{people.filter(p => ['engineer', 'admin'].includes(p.role)).map(p => <option value={p.id} key={p.id}>{p.name}</option>)}</select></Field><Field title="Assignment note"><input name="note" required minLength={5} maxLength={2000} /></Field><button className="button secondary" disabled={busy}>Save assignment</button></form></details>}
      {canEdit && nextAction && <div className="detail-section"><h3>{nextAction === 'VERIFIED' ? 'Independently verify the repair' : 'Progress corrective action'}</h3><p className="muted">Next stage: {label(nextAction)}{nextAction === 'VERIFIED' ? '. A different engineer or administrator must verify.' : '.'}</p><form onSubmit={e => submit(e, `/actions/${current.id}/transition`)}><input type="hidden" name="status" value={nextAction} /><Field title="Work note"><textarea name="note" minLength={5} maxLength={2000} required /></Field>{nextAction === 'VERIFIED' && <Field title="Verification evidence"><textarea name="verification_evidence" required minLength={10} maxLength={4000} placeholder="Describe test procedure, observed results and safe restart evidence." /></Field>}<button className="button" disabled={busy}>{nextAction === 'VERIFIED' ? <ShieldCheck size={16} /> : <Check size={16} />}Mark {label(nextAction)}</button></form></div>}<div className="detail-section"><h3>Permanent action history</h3><div className="timeline">{data.history.map((h: Row) => <div key={h.id}><i /><small>{date(h.occurred_at)}</small><strong>{label(h.from_status || 'Created')} → {label(h.to_status)}</strong><p>{h.note}</p></div>)}</div>{data.audit.map((e: Row) => <div className="subrecord" key={e.id}><div><strong>{label(e.operation)}</strong><small>{date(e.occurred_at)} · {e.user_id}</small></div></div>)}</div></>}
    </div>}
  </Dialog>;
}

function ModalForm({ modal, workspace, plants, people, close, notify }: { modal: Row; workspace: string; plants: Row[]; people: Row[]; close: () => void; notify: (s: string) => void }) {
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [machines, setMachines] = useState<Row[]>([]); const [zones, setZones] = useState<Row[]>([]); const [incidents, setIncidents] = useState<Row[]>([]);
  useEffect(() => { Promise.all([api('/machines?workspace='+workspace+'&limit=100'), api('/config/zones?workspace='+workspace), api('/incidents?workspace='+workspace+'&limit=100&status=ACTIVE')]).then(([m, z, i]) => { setMachines(m.items); setZones(z); setIncidents(i.items); }).catch(e => setError(e.message)); }, [workspace]);
  const resource = modal.resource;
  const initial = modal.initial || {};
  const title = modal.kind === 'action' ? 'Create corrective action' : modal.kind === 'incident' ? 'Open an investigation' : `${modal.initial ? 'Revise' : 'Add'} ${label(resource)}`;
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const values: Row = Object.fromEntries(new FormData(e.currentTarget));
    if (values.due_at) values.due_at = new Date(values.due_at).toISOString();
    if (values.ack_deadline_seconds) values.ack_deadline_seconds = Number(values.ack_deadline_seconds);
    if (resource === 'interlocks') values.mandatory = values.mandatory === 'true';
    setBusy(true); setError('');
    try {
      const path = modal.kind === 'action' ? '/actions' : modal.kind === 'incident' ? '/incidents' : `/config/${resource}${modal.initial ? '/'+initial.id+'/version' : ''}`;
      await api(path, values); notify('Record saved to PostgreSQL.'); close();
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  const selectMachine = <Field title="Machine"><select name="machine_id" defaultValue={initial.machine_id || modal.machine_id || ''} required><option value="" disabled>Select machine</option>{machines.map(m => <option value={m.id} key={m.id}>{m.name}</option>)}</select></Field>;
  const selectPlant = <Field title="Plant"><select name="plant_id" defaultValue={initial.plant_id || modal.plant_id || ''} required><option value="" disabled>Select plant</option>{plants.map(p => <option value={p.id} key={p.id}>{p.name}</option>)}</select></Field>;
  return <Dialog title={title} close={close}><form className="modal-body" onSubmit={submit}>{error && <div className="alert error" role="alert">{error}</div>}
    {modal.kind === 'action' ? <><Field title="Related open incident"><input name="incident_id" list="incident-options" defaultValue={modal.incident_id || ''} required placeholder="Select or paste an incident ID" maxLength={160} /><datalist id="incident-options">{incidents.map(i => <option value={i.id} key={i.id}>{i.title}</option>)}</datalist></Field><Field title="Description"><textarea name="description" required minLength={10} maxLength={4000} /></Field><Field title="Responsible engineer"><select name="assignee_id" required>{people.filter(p => ['engineer', 'admin'].includes(p.role)).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field><Field title="Priority"><select name="priority" defaultValue="HIGH">{['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(p => <option key={p}>{p}</option>)}</select></Field><Field title="Due date & time (local)"><input name="due_at" type="datetime-local" required /></Field></> : modal.kind === 'incident' ? <><input type="hidden" name="alarm_id" value={modal.alarm_id} /><Field title="Investigation title"><input name="title" minLength={10} maxLength={240} required /></Field><p className="muted">The selected alarm, machine and state evidence will be linked automatically.</p></> : <>
      {['machines', 'zones'].includes(resource) && selectPlant}
      {['zones', 'interlocks', 'definitions'].includes(resource) && selectMachine}
      <Field title="Name"><input name="name" defaultValue={initial.name || ''} minLength={3} maxLength={120} required /></Field>
      {resource === 'plants' && <><Field title="Location"><input name="location" minLength={2} maxLength={120} required /></Field><Field title="IANA timezone"><input name="timezone" defaultValue="Asia/Kolkata" required /></Field></>}
      {resource === 'machines' && <Field title="Machine type"><input name="kind" minLength={3} maxLength={80} required placeholder="e.g. Hydraulic press" /></Field>}
      {resource === 'zones' && <Field title="Operating restriction"><input name="restriction" minLength={5} maxLength={240} defaultValue={initial.restriction || 'Guard must be closed while RUNNING'} required /></Field>}
      {resource === 'interlocks' && <><Field title="Safety zone"><select name="zone_id" defaultValue={initial.zone_id || ''} required><option value="" disabled>Select zone assigned to machine</option>{zones.map(z => <option value={z.id} key={z.id}>{z.name} · {shortId(z.id)}</option>)}</select></Field><Field title="Mandatory during operation"><select name="mandatory" defaultValue={String(initial.mandatory ?? true)}><option value="true">Mandatory</option><option value="false">Optional</option></select></Field></>}
      {resource === 'definitions' && <><Field title="Severity"><select name="severity" defaultValue={initial.severity || 'HIGH'}>{['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(s => <option key={s}>{s}</option>)}</select></Field><Field title="Response deadline (seconds)"><input name="ack_deadline_seconds" type="number" min={10} max={86400} defaultValue={initial.ack_deadline_seconds || 300} required /></Field><Field title="Source"><input name="source" defaultValue={initial.source || 'PLC'} required minLength={2} maxLength={80} /></Field></>}
      {modal.initial && <p className="muted">Creates a new effective version. Past events retain their original configuration.</p>}
    </>}
    <div className="modal-actions"><button type="button" className="button secondary" onClick={close}>Cancel</button><button className="button" disabled={busy}>{busy ? 'Saving…' : 'Save record'}</button></div></form></Dialog>;
}

