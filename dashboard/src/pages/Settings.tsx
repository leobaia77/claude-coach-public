import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getMe, setAnthropicKey, clearAnthropicKey, patchSettings, getIntegrations, connectHevy, disconnectIntegration, saveDexa, type MeResponse } from '../coachApi'
import { signOut } from '../authClient'

export function Settings() {
  const [me, setMe] = useState<MeResponse | null>(null)
  const [keyInput, setKeyInput] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => getMe().then(setMe).catch(() => setMe(null))
  useEffect(() => { void load() }, [])

  const saveKey = async () => {
    setBusy(true); setMsg('')
    try {
      const r = await setAnthropicKey(keyInput.trim())
      setMsg(`Key saved (…${r.last4})`)
      setKeyInput('')
      await load()
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'failed')
    }
    setBusy(false)
  }

  const removeKey = async () => {
    await clearAnthropicKey()
    setMsg('Key removed')
    await load()
  }

  const changeSetting = async (patch: Record<string, unknown>) => {
    await patchSettings(patch)
    await load()
  }

  if (!me) return <div className="page"><p>Loading…</p></div>
  const s = me.settings

  return (
    <div className="page">
      <div className="page-head">
        <h1>Settings</h1>
        <div className="page-head-actions">
          <Link to="/">← Dashboard</Link>
          <button className="link-btn" onClick={() => void signOut()}>Sign out</button>
        </div>
      </div>

      <section className="card">
        <h2>Anthropic API key</h2>
        <p className="muted">Your coach runs on your own Anthropic account. Get a key at console.anthropic.com. Typical cost $5–30/mo depending on use.</p>
        {s?.hasAnthropicKey ? (
          <div className="row">
            <span className="ok">✓ Key set (…{s.anthropicKeyLast4})</span>
            <button className="link-btn danger" onClick={() => void removeKey()}>Remove</button>
          </div>
        ) : (
          <div className="row">
            <input type="password" placeholder="sk-ant-…" value={keyInput} onChange={(e) => setKeyInput(e.target.value)} />
            <button onClick={() => void saveKey()} disabled={busy || !keyInput.trim()}>Save & validate</button>
          </div>
        )}
        {msg && <div className="muted" style={{ marginTop: 8 }}>{msg}</div>}
      </section>

      <IntegrationsSection />

      <section className="card">
        <h2>Preferences</h2>
        <div className="pref-row">
          <label>Coach model</label>
          <select value={s?.coachModel} onChange={(e) => void changeSetting({ coachModel: e.target.value })}>
            <option value="claude-sonnet-4-6">Sonnet (balanced)</option>
            <option value="claude-opus-4-8">Opus (deepest)</option>
            <option value="claude-haiku-4-5-20251001">Haiku (fastest/cheapest)</option>
          </select>
        </div>
        <div className="pref-row">
          <label>Weight unit</label>
          <select value={s?.weightUnit} onChange={(e) => void changeSetting({ weightUnit: e.target.value })}>
            <option value="lb">lb</option>
            <option value="kg">kg</option>
          </select>
        </div>
        <div className="pref-row">
          <label>Timezone</label>
          <input defaultValue={s?.timezone} onBlur={(e) => void changeSetting({ timezone: e.target.value })} />
        </div>
        <div className="pref-row">
          <label>Weekly summary email</label>
          <input type="checkbox" checked={!!s?.weeklyEmail} onChange={(e) => void changeSetting({ weeklyEmail: e.target.checked })} />
        </div>
      </section>

      {me.user.role === 'admin' && (
        <section className="card">
          <h2>Admin</h2>
          <Link to="/admin">Manage invites & users →</Link>
        </section>
      )}
    </div>
  )
}

const PROVIDER_INFO: Record<string, { name: string; blurb: string; steps: string[] }> = {
  hevy: {
    name: 'Hevy',
    blurb: 'Strength workouts — sets, reps, weights, routines.',
    steps: [
      'Open the Hevy app → Settings → Developer (needs Hevy Pro).',
      'Tap "Generate API Key" and copy it.',
      'Paste it below and press Connect.',
    ],
  },
  strava: {
    name: 'Strava',
    blurb: 'Rides & runs — power, HR, cadence, segments, GPS streams.',
    steps: [
      'Press "Connect Strava" below.',
      'Strava opens — log in and press "Authorize".',
      "You'll bounce back here and it'll show connected. No keys to copy.",
    ],
  },
  oura: {
    name: 'Oura',
    blurb: 'Recovery — HRV, resting HR, sleep, readiness.',
    steps: [
      'Press "Connect Oura" below.',
      'Oura opens — log in and press "Allow".',
      'You return here connected. No keys to copy.',
    ],
  },
  garmin: {
    name: 'Garmin',
    blurb: 'Rides, runs, daily health. Coming soon.',
    steps: ['Not available yet — use Strava for activity data in the meantime.'],
  },
}

function IntegrationsSection() {
  const [data, setData] = useState<Awaited<ReturnType<typeof getIntegrations>> | null>(null)
  const [hevyKey, setHevyKey] = useState('')
  const [msg, setMsg] = useState('')

  const load = () => getIntegrations().then(setData).catch(() => {})
  useEffect(() => { void load() }, [])

  if (!data) return <section className="card"><h2>Integrations</h2><p className="muted">Loading…</p></section>
  const status = (p: string) => data.integrations.find((i) => i.provider === p)

  const saveHevy = async () => {
    setMsg('')
    try { await connectHevy(hevyKey.trim()); setHevyKey(''); await load() }
    catch (e) { setMsg(e instanceof Error ? e.message : 'failed') }
  }
  const disconnect = async (p: string) => { await disconnectIntegration(p); await load() }

  return (
    <section className="card">
      <h2>Integrations</h2>
      <p className="muted">Connect your data sources so the coach pulls your real training. Each is yours alone — other users never see your data.</p>
      {(['hevy', 'strava', 'oura', 'garmin'] as const).map((p) => {
        const info = PROVIDER_INFO[p]
        const st = status(p)
        const on = st?.status === 'connected'
        const available = data.available[p]
        return (
          <div key={p} className="integration-block">
            <div className="integration-row">
              <span className="integration-name">{info.name}</span>
              {on
                ? <span className="ok">✓ connected <button className="link-btn danger" onClick={() => void disconnect(p)}>disconnect</button></span>
                : available && p !== 'hevy'
                  ? <a className="connect-btn" href={`/api/integrations/${p}/authorize`}>Connect {info.name}</a>
                  : !available
                    ? <span className="muted">{p === 'garmin' ? 'coming soon' : 'not enabled yet'}</span>
                    : null}
            </div>
            <div className="integration-how muted">{info.blurb}</div>
            {!on && (available || p === 'hevy') && (
              <ol className="how-steps">{info.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
            )}
            {!on && !available && p !== 'garmin' && (
              <div className="integration-how muted">The app owner needs to enable {info.name} once — then a Connect button appears here for everyone.</div>
            )}
            {p === 'hevy' && !on && (
              <div className="row" style={{ marginTop: 8 }}>
                <input type="password" placeholder="Paste Hevy API key" value={hevyKey} onChange={(e) => setHevyKey(e.target.value)} />
                <button onClick={() => void saveHevy()} disabled={!hevyKey.trim()}>Connect</button>
              </div>
            )}
          </div>
        )
      })}
      {msg && <div className="auth-err" style={{ marginTop: 8 }}>{msg}</div>}
      <DexaBlock />
    </section>
  )
}

function DexaBlock() {
  const [date, setDate] = useState('')
  const [bf, setBf] = useState('')
  const [lean, setLean] = useState('')
  const [msg, setMsg] = useState('')

  const save = async () => {
    setMsg('')
    try {
      const r = await saveDexa({
        date: date || undefined,
        bodyFatPct: bf ? Number(bf) : undefined,
        leanMassLb: lean ? Number(lean) : undefined,
      })
      setMsg(`Saved ${r.saved} value(s).`)
      setBf(''); setLean('')
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'failed')
    }
  }

  return (
    <div className="integration-block">
      <div className="integration-row">
        <span className="integration-name">DEXA / body composition</span>
        <span className="muted">manual</span>
      </div>
      <div className="integration-how muted">No scan API exists — after each DEXA scan, type the numbers here (or just tell your coach in chat).</div>
      <div className="dexa-form">
        <label>Scan date<input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
        <label>Body fat %<input type="number" step="0.1" placeholder="18.4" value={bf} onChange={(e) => setBf(e.target.value)} /></label>
        <label>Lean mass (lb)<input type="number" step="0.1" placeholder="186.8" value={lean} onChange={(e) => setLean(e.target.value)} /></label>
        <button onClick={() => void save()} disabled={!bf && !lean}>Save scan</button>
      </div>
      {msg && <div className="muted" style={{ marginTop: 6 }}>{msg}</div>}
    </div>
  )
}
