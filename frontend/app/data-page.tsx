'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowDownToLine, ArrowRight, CheckCheck, Database, Plus, ShieldCheck } from 'lucide-react';
import { api, Badge, Field, Row, fmt, date, label, shortId } from './ui';
import { useResource } from './resources';

const rules: Record<string, { name: string; expected: string }> = {
  ACK_BEFORE_ALARM: { name: 'Acknowledgement before alarm', expected: 'An acknowledgement must occur at or after the alarm.' },
  IMPOSSIBLE_INTERLOCK_STATE: { name: 'Unsafe interlock state', expected: 'A running machine must have its mandatory guard closed and interlock engaged.' },
  INCIDENT_MISSING_CONTEXT: { name: 'Incident missing triggering evidence', expected: 'Every incident needs a triggering alarm and matching machine-state evidence.' },
  DUPLICATE_ALARM_REPLAY: { name: 'Duplicate alarm replay', expected: 'Each physical source event must count once, even when ingested again.' },
  ACTION_CLOSED_UNVERIFIED: { name: 'Action closed without verification', expected: 'Closure requires completed work, an independent verifier and verification evidence.' },
  ALARM_FLOOD: { name: 'Alarm flood', expected: 'Distinct alarm volume should stay below the configured rolling-window threshold.' },
  NUISANCE_ALARM: { name: 'Repeated nuisance alarms', expected: 'Repeated low-severity sensor chatter should be investigated and reduced.' },
  RECURRENT_HAZARD: { name: 'Hazard after verified remediation', expected: 'A verified repair should prevent the same hazard recurring on the machine.' },
};
const evidenceLabels: Record<string, string> = {
  alarm_at: 'Alarm occurred', acknowledged_at: 'Acknowledged', machine_state: 'Machine operating state',
  guard: 'Guard position', interlock: 'Interlock state', machine_id: 'Machine', triggering_alarm_count: 'Triggering alarms',
  source_event_id: 'Physical source event', original_record_id: 'Original alarm', status: 'Action status',
  verified_at: 'Verified', evidence: 'Verification evidence', count: 'Distinct occurrences', window_seconds: 'Time window',
  definition_id: 'Alarm definition', day: 'UTC day', previous_incident_id: 'Previous incident', action_id: 'Corrective action',
};
const summaryEntities = [
  ['plants', 'Plants'], ['machines', 'Machines'], ['alarm_definitions', 'Alarm definitions'],
  ['alarm_events', 'Alarm events'], ['incidents', 'Incidents'], ['corrective_actions', 'Corrective actions'],
];

function referenceLink(entity: string, id: string, finding?: Row): string | undefined {
  if (entity === 'alarm_events') return '/alarms?detail='+encodeURIComponent(id);
  if (entity === 'incidents') return '/incidents?detail='+encodeURIComponent(id);
  if (entity === 'corrective_actions') return '/actions?detail='+encodeURIComponent(id);
  if (entity === 'machines') return '/machines?detail='+encodeURIComponent(id);
  if (entity === 'acknowledgements') {
    const alarm = finding?.affected_record_ids?.find((r: string) => r.startsWith('ALM-'));
    if (alarm) return referenceLink('alarm_events', alarm);
  }
  if (entity === 'interlock_state_events' && finding?.evidence?.machine_id) return referenceLink('machines', finding.evidence.machine_id);
}

function EvidenceValue({ name, value }: { name: string; value: unknown }) {
  if (value === null || value === undefined || value === '') return <span>Not recorded</span>;
  if (Array.isArray(value)) return <span>{value.map(String).join(' · ') || 'None'}</span>;
  if (typeof value === 'object') return <dl className="evidence-values">{Object.entries(value).map(([key, v]) => <div key={key}><dt>{evidenceLabels[key] || label(key)}</dt><dd><EvidenceValue name={key} value={v} /></dd></div>)}</dl>;
  if (name === 'window_seconds') return <span>{Number(value)/60} minutes</span>;
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value)) return <time dateTime={value}>{date(value)}</time>;
  if (name === 'day') return <span>{new Date(String(value)).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })}</span>;
  const entity = ({ machine_id: 'machines', original_record_id: 'alarm_events', previous_incident_id: 'incidents', action_id: 'corrective_actions' } as Record<string, string>)[name];
  if (entity) return <Link className="text-link evidence-reference" href={referenceLink(entity, String(value))!}>{shortId(String(value))}<ArrowRight size={12} /></Link>;
  return <span>{typeof value === 'boolean' ? value ? 'Yes' : 'No' : typeof value === 'number' ? fmt(value) : /^[A-Z_]+$/.test(String(value)) ? label(String(value)) : String(value)}</span>;
}

function Finding({ finding }: { finding: Row }) {
  const definition = rules[finding.rule_id];
  const href = referenceLink(finding.target_entity, finding.target_record_id, finding);
  const status = finding.missed ? 'Expected · not detected' : finding.expected ? 'Expected anomaly · detected' : definition && ['ALARM_FLOOD', 'NUISANCE_ALARM', 'RECURRENT_HAZARD'].includes(finding.rule_id) ? 'Operational finding' : 'Unexpected finding';
  let explanation = finding.explanation;
  if (finding.rule_id === 'ACK_BEFORE_ALARM' && finding.evidence?.alarm_at && finding.evidence?.acknowledged_at) {
    const difference = (new Date(finding.evidence.alarm_at).getTime()-new Date(finding.evidence.acknowledged_at).getTime())/1000;
    explanation = `The acknowledgement occurred ${difference < 60 ? `${Math.round(difference)} seconds` : `${(difference/60).toFixed(1)} minutes`} before the alarm was generated.`;
  }
  return <details className="readable-finding"><summary><span className="finding-title">{definition?.name || label(finding.rule_id)}<small>{date(finding.occurred_at)}</small></span><Badge value={finding.severity || 'HIGH'} /><span className={`finding-state ${finding.missed ? 'danger' : ''}`}>{status}</span></summary><div className="finding-content"><p>{explanation}</p><div className="expected-condition"><strong>Expected condition</strong><p>{definition?.expected || 'The record should satisfy its documented safety rule.'}</p></div><div className="affected-reference"><span>Affected {finding.target_entity === 'incidents' ? 'incident' : finding.target_entity === 'corrective_actions' ? 'action' : 'record'}</span>{href ? <Link href={href} className="text-link" title={finding.target_record_id}>{shortId(finding.target_record_id)}<ArrowRight size={13} /></Link> : <span title={finding.target_record_id}>{shortId(finding.target_record_id)}</span>}</div><dl className="evidence-values">{Object.entries(finding.evidence || {}).map(([key, value]) => <div key={key}><dt>{evidenceLabels[key] || label(key)}</dt><dd><EvidenceValue name={key} value={value} /></dd></div>)}</dl>{finding.missed && <p className="muted">This scenario was expected in the evaluation labels but was not identified by the latest detection run.</p>}</div></details>;
}

type Props = { runs: Row[]; workspace: string; role: string; notify: (s: string) => void; select: (id: string) => void };

export default function DataPage({ runs, workspace, role, notify, select }: Props) {
  const [preset, setPreset] = useState('starter');
  const [seed, setSeed] = useState(20261022);
  const [parameters, setParameters] = useState({ plants: 2, machines: 8, definitions: 24, events: 800, days: 7, anomaly_rate: 0.005 });
  const reportResource = useResource<Row>(role === 'admin' && workspace !== 'manual' ? `/datasets/${workspace}/report` : null, true);
  const report = reportResource.data?.report;
  const loading = reportResource.loading;
  const [repro, setRepro] = useState<Row | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [rule, setRule] = useState('');
  const [page, setPage] = useState(1);
  const [validationPage, setValidationPage] = useState(1);
  useEffect(() => { setParameters(preset === 'full' ? { plants: 4, machines: 60, definitions: 200, events: 50000, days: 30, anomaly_rate: 0.005 } : { plants: 2, machines: 8, definitions: 24, events: 800, days: 7, anomaly_rate: 0.005 }); }, [preset]);
  useEffect(() => { setPage(1); }, [rule, workspace]);
  useEffect(() => { setRepro(null); setValidationPage(1); }, [workspace]);
  if (role !== 'admin') return null;

  const run = runs.find(r => r.id === workspace);
  const counts = run?.counts || {};
  const generatedRecords = Object.entries(counts).reduce((sum, [key, value]) => key === 'ground_truth' ? sum : sum+Number(value), 0);
  const inProgress = runs.find(r => ['QUEUED', 'RUNNING'].includes(r.status));
  const truth: Row[] = report?.ground_truth || [];
  const expectedKeys = new Set(truth.map(t => `${t.rule_id}:${t.target_record_id}`));
  const detectedKeys = new Set<string>(report?.detections?.map((d: Row) => `${d.rule_id}:${d.target_record_id}`) || []);
  const findings: Row[] = [
    ...(report?.detections || []).map((d: Row) => ({ ...d, expected: expectedKeys.has(`${d.rule_id}:${d.target_record_id}`) })),
    ...truth.filter(t => !detectedKeys.has(`${t.rule_id}:${t.target_record_id}`)).map(t => ({ ...t, missed: true, severity: 'HIGH', occurred_at: null, evidence: {} })),
  ];
  const filtered = findings.filter(f => !rule || f.rule_id === rule);
  const exceptions: Row[] = report?.validation?.findings || [];
  const metrics = report?.evaluation?.overall;

  async function generateData(event: FormEvent) {
    event.preventDefault(); setBusy('generate'); setError('');
    try {
      const result = await api('/datasets', { preset, seed, ...parameters });
      if (result.status === 'COMPLETED') select(result.id);
      notify(result.status === 'COMPLETED' ? 'This dataset already exists. Saved records were preserved.' : 'Dataset generation started.');
    } catch (e) { setError((e as Error).message); } finally { setBusy(''); }
  }
  async function validate() {
    setBusy('validate'); setError('');
    try { reportResource.setData({ report: await api(`/datasets/${workspace}/validate`, {}) }); notify('Validation and detection evaluation completed.'); }
    catch (e) { setError((e as Error).message); } finally { setBusy(''); }
  }
  async function reproduce() {
    setBusy('reproduce'); setError('');
    try { const result = await api(`/datasets/${workspace}/reproduce`, {}); setRepro(result); notify(result.identical ? 'Both generated datasets are identical.' : 'The generated datasets differ.'); }
    catch (e) { setError((e as Error).message); } finally { setBusy(''); }
  }
  function download(format: string) { return `/api/datasets/${workspace}/export?format=${format}`; }
  const available = !!report && run?.status === 'COMPLETED';

  return <div className="data-workspace">
    {(error || reportResource.error) && <div className="alert error" role="alert">{error || reportResource.error}</div>}
    <section className="panel data-section" aria-labelledby="generation-title">
      <div className="panel-heading"><div className="numbered-heading"><span>01</span><div><h2 id="generation-title">Dataset Generation</h2><p>Create a repeatable synthetic safety simulation or inspect an existing dataset.</p></div></div><Database size={19} /></div>
      <div className="generation-layout"><form onSubmit={generateData}>
        <div className="preset-toggle">{['starter', 'full'].map(p => <button type="button" key={p} className={preset === p ? 'selected' : ''} onClick={() => setPreset(p)}><strong>{label(p)} dataset</strong><small>{p === 'full' ? '4 plants · 60 machines · 50,000 alarms · 30 days' : '2 plants · 8 machines · 800 alarms · 7 days'}</small></button>)}</div>
        <div className="generation-controls"><Field title="Random seed"><input type="number" min={0} max={4294967295} value={seed} onChange={e => setSeed(Number(e.target.value))} required /></Field><button className="button" disabled={!!busy || !!inProgress}><Plus size={16} />{busy === 'generate' ? 'Starting…' : 'Generate dataset'}</button></div>
        <details className="compact-details"><summary>Advanced generation options</summary><div className="form-grid advanced">{Object.entries(parameters).map(([key, value]) => <Field key={key} title={key === 'anomaly_rate' ? 'Anomaly injection rate' : label(key)}><input type="number" step={key === 'anomaly_rate' ? 0.001 : 1} min={key === 'anomaly_rate' ? 0.001 : key === 'events' ? 100 : 1} max={key === 'events' ? 200000 : key === 'days' ? 90 : key === 'anomaly_rate' ? 0.05 : key === 'plants' ? 20 : key === 'machines' ? 500 : 2000} value={value} onChange={e => setParameters(p => ({ ...p, [key]: Number(e.target.value) }))} required /></Field>)}</div></details>
        <p className="generation-note">Existing datasets and manual records are preserved.</p>
      </form><div className="selected-dataset"><Field title="Dataset"><select aria-label="Dataset" value={workspace} onChange={e => select(e.target.value)}><option value="manual">Select a generated dataset</option>{runs.filter(r => r.status === 'COMPLETED').map(r => <option key={r.id} value={r.id}>{label(r.config.preset)} · {fmt(r.config.events)} alarms · seed {r.config.seed}</option>)}</select></Field>
        {inProgress ? <div className="generation-status" role="status"><Badge value={inProgress.status} /><progress value={inProgress.progress} max={100} /><span>{inProgress.progress}% complete · seed {inProgress.config.seed}</span></div> : run ? <div className="generation-status"><Badge value={run.status} /><span>{run.config.days}-day simulation · seed {run.config.seed}</span><small>Created {date(run.created_at)}</small></div> : <p className="muted">Generate or select a dataset to review its integrity and findings.</p>}
        <details className="compact-details"><summary>Generation history · {runs.length} runs</summary><div className="compact-history">{runs.slice(0, 8).map(r => <div key={r.id}><div><strong>{label(r.config.preset)} · seed {r.config.seed}</strong><small>{date(r.created_at)} · {fmt(r.config.events)} alarms</small>{r.status === 'FAILED' && <p className="danger">Generation failed. Retry the same configuration or review the administrator logs.</p>}</div><Badge value={r.status} />{r.status === 'COMPLETED' && <button type="button" className="text-link" onClick={() => select(r.id)}>Inspect<ArrowRight size={12} /></button>}</div>)}</div><small className="muted">Showing the latest eight runs.</small></details>
      </div></div>
      {run && <div className="core-inventory">{summaryEntities.map(([key, title]) => <div key={key}><span>{title}</span><strong>{fmt(counts[key])}</strong></div>)}</div>}
    </section>

    {loading && !report && <div className="loading" role="status">Loading dataset results…</div>}
    <section className="panel data-section" aria-labelledby="integrity-title"><div className="panel-heading"><div className="numbered-heading"><span>02</span><div><h2 id="integrity-title">Dataset Integrity</h2><p>Check record consistency and distinguish expected scenarios from defects.</p></div></div><button className="button secondary" disabled={!!busy || !available} onClick={validate}><ShieldCheck size={14} />{busy === 'validate' ? 'Validating…' : 'Run validation'}</button></div>
      {report ? <><div className="integrity-summary"><div><span>Total generated records</span><strong>{fmt(generatedRecords)}</strong></div><div><span>Validation status</span><Badge value={report.validation.status} /></div><div><span>Expected anomalies</span><strong>{fmt(truth.length)}</strong></div><div><span>Unexpected failures</span><strong className={report.validation.counts.UNEXPECTED_FAILURE ? 'danger' : ''}>{fmt(report.validation.counts.UNEXPECTED_FAILURE)}</strong></div></div><p className="integrity-note">{fmt(report.validation.checks)} structural checks · {fmt(report.validation.counts.EXPECTED_ANOMALY)} expected findings. One anomaly may produce several related findings.</p>
      <details className="compact-details section-details"><summary>Validation results · {fmt(exceptions.length)} findings</summary><div className="table-scroll"><table><thead><tr><th>Check</th><th>Affected record</th><th>Result</th></tr></thead><tbody>{exceptions.slice((validationPage-1)*10, validationPage*10).map((f, i) => <tr key={i}><td><strong>{rules[f.check]?.name || label(f.check)}</strong><small className="cell-note">{f.description}</small></td><td title={f.record_id}>{shortId(f.record_id)}</td><td><Badge value={f.category} /></td></tr>)}</tbody></table></div>{exceptions.length > 10 && <div className="pagination"><span>Page {validationPage} of {Math.ceil(exceptions.length/10)}</span><div><button className="button secondary" disabled={validationPage === 1} onClick={() => setValidationPage(p => p-1)}>Previous</button><button className="button secondary" disabled={validationPage*10 >= exceptions.length} onClick={() => setValidationPage(p => p+1)}>Next</button></div></div>}</details>
      <details className="compact-details section-details"><summary>Detailed Record Counts</summary><div className="inventory">{Object.entries(counts).map(([key, value]) => <div key={key}><span>{label(key)}</span><strong>{fmt(Number(value))}</strong></div>)}</div></details></> : <p className="section-empty">Select a completed dataset to inspect validation results.</p>}
    </section>

    <section className="panel data-section" aria-labelledby="evaluation-title"><div className="panel-heading"><div className="numbered-heading"><span>03</span><div><h2 id="evaluation-title">Detection Evaluation</h2><p>Compare expected scenarios with findings from the latest detection run.</p></div></div><ShieldCheck size={19} /></div>
      {report && metrics ? <><div className="evaluation-scores">{['precision', 'recall', 'f1'].map(key => <div key={key}><span>{key === 'f1' ? 'F1-score' : label(key)}</span><strong>{(metrics[key]*100).toFixed(1)}<small>%</small></strong></div>)}<div><span>Labelled anomalies detected</span><strong>{fmt(metrics.tp)}<small> / {fmt(metrics.tp+metrics.fn)}</small></strong></div></div>
      <div className="table-scroll evaluation-comparison"><table><thead><tr><th>Anomaly</th><th>Expected</th><th>Detected</th><th>Missed</th><th>Unexpected</th></tr></thead><tbody>{Object.entries(report.evaluation.per_type).map(([key, value]) => { const v = value as Row; return <tr key={key}><td>{rules[key]?.name || label(key)}</td><td>{fmt(v.tp+v.fn)}</td><td>{fmt(v.tp+v.fp)}</td><td>{fmt(v.fn)}</td><td>{fmt(v.fp)}</td></tr>; })}</tbody></table></div>
      <div className="evaluation-note">Results describe this synthetic dataset and do not establish real-world detection accuracy.</div>
      <div className="findings-toolbar"><div><h3>Explainable rule findings</h3><p>Readable evidence for each safety decision.</p></div><Field title="Anomaly type"><select aria-label="Rule filter" value={rule} onChange={e => setRule(e.target.value)}><option value="">All findings</option>{Array.from(new Set(findings.map(f => f.rule_id))).map(key => <option key={key} value={key}>{rules[key]?.name || label(key)}</option>)}</select></Field></div>
      <div className="finding-list">{filtered.slice((page-1)*10, page*10).map((finding, i) => <Finding key={`${finding.rule_id}:${finding.target_record_id}:${i}`} finding={finding} />)}{!filtered.length && <p className="section-empty">No findings match this anomaly type.</p>}</div><div className="pagination"><span>{filtered.length ? `${(page-1)*10+1}–${Math.min(page*10, filtered.length)} of ${fmt(filtered.length)} findings` : '0 findings'}</span><div><button className="button secondary" disabled={page === 1} onClick={() => setPage(p => p-1)}>Previous</button><button className="button secondary" disabled={page*10 >= filtered.length} onClick={() => setPage(p => p+1)}>Next</button></div></div>
      <details className="compact-details section-details"><summary>Evaluation details</summary><p className="muted">True positives {fmt(metrics.tp)} · false positives {fmt(metrics.fp)} · true negatives {fmt(metrics.tn)} · false negatives {fmt(metrics.fn)}. Each rule is evaluated against its eligible records, including normal records. Labels are compared only after detection.</p></details></> : <p className="section-empty">Select a completed dataset to review detection performance and evidence.</p>}
    </section>

    <section className="panel data-section" aria-labelledby="exports-title"><div className="panel-heading"><div className="numbered-heading"><span>04</span><div><h2 id="exports-title">Exports & Reproducibility</h2><p>Download complete records and confirm the same inputs produce the same output.</p></div></div><ArrowDownToLine size={19} /></div>
      <div className="export-controls">{[['csv', 'Export CSV'], ['json', 'Export JSON'], ['sql', 'Export SQL'], ['validation', 'Download validation report'], ['ground-truth', 'Download ground-truth report'], ['bundle', 'Export bundle']].map(([format, title]) => available ? <a key={format} className="button secondary" href={download(format)}><ArrowDownToLine size={14} />{title}</a> : <button key={format} className="button secondary" disabled><ArrowDownToLine size={14} />{title}</button>)}</div>
      <div className="reproduction-row"><div><h3>Reproducibility check</h3><p>Compare two fresh runs using the same seed, scale and time window.</p></div><button className="button" disabled={!!busy || !available} onClick={reproduce}><CheckCheck size={15} />{busy === 'reproduce' ? 'Comparing runs…' : 'Test reproducibility'}</button></div>
      {repro && <div className={`alert reproduction-result ${repro.identical ? 'success' : 'error'}`} role="status"><CheckCheck size={18} /><div><strong>{repro.identical ? 'Reproducible: both runs match' : 'Reproducibility mismatch detected'}</strong><p>{repro.identical ? 'Record counts, canonical records and entity checksums are identical.' : 'Review the downloaded technical reports to investigate the differences.'}</p></div></div>}
    </section>
  </div>;
}
