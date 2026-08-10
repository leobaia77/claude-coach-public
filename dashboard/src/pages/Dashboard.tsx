import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { getMe, getCoachReports, coachReportUrl, patchSettings, uploadDocument, streamCoach, type MeResponse } from '../coachApi'
import { ChatBox } from '../ChatBox'

interface ReportRow { id: string; title: string; date: string; type: string; summary: string; file: string }

const QUICK = [
  { label: 'Weekly check-in', kind: 'weekly' as const, prompt: 'Run my weekly check-in.' },
  { label: 'Analyze last ride', kind: 'chat' as const, prompt: 'Analyze my last ride in full (Appendix B).' },
  { label: 'Analyze last workout', kind: 'chat' as const, prompt: 'Analyze my last strength workout and give next-session targets.' },
]

export function Dashboard() {
  const [me, setMe] = useState<MeResponse | null>(null)
  const [reports, setReports] = useState<ReportRow[]>([])

  useEffect(() => {
    void getMe().then(setMe).catch(() => {})
    void getCoachReports().then(setReports).catch(() => {})
  }, [])

  const noKey = me && !me.settings?.hasAnthropicKey

  return (
    <div className="dash">
      <header className="dash-head">
        <div className="dash-brand">🏋️ Coach{me ? ` · ${me.user.name.split(' ')[0]}` : ''}</div>
        <nav>
          {me?.user.role === 'admin' && <Link to="/admin">Admin</Link>}
          <Link to="/settings">Settings</Link>
        </nav>
      </header>

      {noKey && (
        <div className="banner">
          Add your Anthropic API key to start coaching. <Link to="/settings">Go to Settings →</Link>
        </div>
      )}

      <GoalsCard goals={me?.settings?.goals ?? null} onSaved={() => void getMe().then(setMe)} />

      <UploadCard hasKey={!noKey} />

      <main className="dash-grid">
        <section className="dash-chat card">
          <h2>Coach</h2>
          <div className="quick-actions">
            {QUICK.map((q) => (
              <QuickButton key={q.label} label={q.label} />
            ))}
          </div>
          <ChatBox kind="chat" seed="What can I help you train today?" />
        </section>

        <aside className="dash-reports card">
          <h2>Reports</h2>
          {reports.length === 0 && <p className="muted">No reports yet — they appear here after your coach evaluates a ride or workout.</p>}
          <ul className="report-list">
            {reports.map((r) => (
              <li key={r.id}>
                <a href={coachReportUrl(r.file)} target="_blank" rel="noopener">
                  <span className="report-date">{r.date}</span>
                  <span className="report-title">{r.title}</span>
                </a>
              </li>
            ))}
          </ul>
        </aside>
      </main>
    </div>
  )
}

// Quick-action buttons submit a canned prompt by dispatching a custom event the
// ChatBox could listen to; for simplicity we just render them as hints for now.
function QuickButton({ label }: { label: string }) {
  return <span className="quick-hint">{label}</span>
}

function UploadCard({ hasKey }: { hasKey: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [status, setStatus] = useState<'idle' | 'uploading' | 'processing' | 'done' | 'error'>('idle')
  const [detail, setDetail] = useState('')

  const onPick = async (file: File | undefined) => {
    if (!file) return
    setStatus('uploading')
    setDetail(`Uploading ${file.name}…`)
    try {
      const { relPath } = await uploadDocument(file)
      if (!hasKey) {
        setStatus('done')
        setDetail(`Uploaded ✓ — add your API key in Settings, then ask the coach to process ${relPath}.`)
        return
      }
      setStatus('processing')
      setDetail('Uploaded ✓ — coach is reading it…')
      let acc = ''
      await streamCoach(
        `I just uploaded a document to ${relPath}. Read it, extract the meaningful data (labs, DEXA, body-comp, notes), and write it into the correct place in my wiki/memory. Then tell me exactly what you added.`,
        undefined,
        'chat',
        {
          onText: (t) => { acc += t; setDetail(acc) },
          onDone: () => setStatus('done'),
          onError: (e) => { setStatus('error'); setDetail(acc || e) },
        },
      )
    } catch (e) {
      setStatus('error')
      setDetail(e instanceof Error ? e.message : 'upload failed')
    }
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <section className="card upload-card">
      <div className="goals-head">
        <h2>📄 Add a document</h2>
        <button
          className="connect-btn"
          onClick={() => inputRef.current?.click()}
          disabled={status === 'uploading' || status === 'processing'}
        >
          {status === 'uploading' ? 'Uploading…' : status === 'processing' ? 'Processing…' : 'Upload'}
        </button>
      </div>
      <p className="muted">Lab report, DEXA scan, physique photo, or CSV (PDF / image / csv, ≤25MB). The coach reads it and files the data into your wiki &amp; memory.</p>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.webp,.heic,.csv,.txt,.md"
        style={{ display: 'none' }}
        onChange={(e) => void onPick(e.target.files?.[0])}
      />
      {detail && <div className={`upload-detail ${status === 'error' ? 'auth-err' : 'muted'}`}>{detail}</div>}
    </section>
  )
}

function GoalsCard({ goals, onSaved }: { goals: string | null; onSaved: () => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(goals ?? '')
  const [busy, setBusy] = useState(false)

  useEffect(() => setDraft(goals ?? ''), [goals])

  const save = async () => {
    setBusy(true)
    try {
      await patchSettings({ goals: draft })
      setEditing(false)
      onSaved()
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card goals-card">
      <div className="goals-head">
        <h2>🎯 My goal</h2>
        {!editing && (
          <button className="link-btn" onClick={() => setEditing(true)}>
            {goals ? 'Edit' : 'Set goal'}
          </button>
        )}
      </div>
      {editing ? (
        <div className="goals-edit">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            placeholder="e.g. Hit a 1,000 lb powerlifting total by October, then pivot to a 12h endurance ride."
            autoFocus
          />
          <div className="goals-actions">
            <button onClick={() => void save()} disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
            <button className="link-btn" onClick={() => { setEditing(false); setDraft(goals ?? '') }}>Cancel</button>
          </div>
        </div>
      ) : goals ? (
        <p className="goals-text">{goals}</p>
      ) : (
        <p className="muted">No goal set yet — tell your coach what you're working toward.</p>
      )}
    </section>
  )
}
