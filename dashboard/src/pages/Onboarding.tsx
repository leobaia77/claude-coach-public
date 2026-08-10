import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMe, setAnthropicKey, advanceOnboarding, type MeResponse } from '../coachApi'
import { ChatBox } from '../ChatBox'

type Step = 'anthropic_key' | 'integrations' | 'intake'

export function Onboarding() {
  const nav = useNavigate()
  const [me, setMe] = useState<MeResponse | null>(null)
  const [step, setStep] = useState<Step>('anthropic_key')
  const [keyInput, setKeyInput] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getMe().then((m) => {
      setMe(m)
      if (m.user.onboardingStage === 'done') { nav('/'); return }
      if (m.settings?.hasAnthropicKey) setStep(m.user.onboardingStage === 'account' ? 'integrations' : (m.user.onboardingStage as Step))
    }).catch(() => {})
  }, [nav])

  const saveKey = async () => {
    setBusy(true); setErr('')
    try {
      await setAnthropicKey(keyInput.trim())
      await advanceOnboarding('integrations')
      setStep('integrations')
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'failed')
    }
    setBusy(false)
  }

  const toIntake = async () => {
    await advanceOnboarding('intake')
    setStep('intake')
  }

  const finish = async () => {
    await advanceOnboarding('done')
    nav('/')
  }

  return (
    <div className="page onboarding">
      <div className="onb-steps">
        <span className={step === 'anthropic_key' ? 'active' : 'done'}>1 · API key</span>
        <span className={step === 'integrations' ? 'active' : step === 'intake' ? 'done' : ''}>2 · Connect data</span>
        <span className={step === 'intake' ? 'active' : ''}>3 · Meet your coach</span>
      </div>

      {step === 'anthropic_key' && (
        <section className="card">
          <h1>Add your Anthropic API key</h1>
          <p className="muted">
            Your coach runs on your own Anthropic account — you stay in control of usage and cost
            (typically $5–30/mo). Create a key at <b>console.anthropic.com</b>, then paste it below.
            It's encrypted at rest and validated live before saving.
          </p>
          <div className="row">
            <input type="password" placeholder="sk-ant-…" value={keyInput} onChange={(e) => setKeyInput(e.target.value)} />
            <button onClick={() => void saveKey()} disabled={busy || !keyInput.trim()}>{busy ? 'Validating…' : 'Save & continue'}</button>
          </div>
          {err && <div className="auth-err">{err}</div>}
        </section>
      )}

      {step === 'integrations' && (
        <section className="card">
          <h1>Connect your training data</h1>
          <p className="muted">
            Hevy (strength), Strava &amp; Garmin (rides/runs), Oura (recovery). One-click connection
            arrives with the integrations release — for now you can skip this and connect later in
            Settings. Your coach still works from what you tell it.
          </p>
          <button onClick={() => void toIntake()}>Continue to intake →</button>
        </section>
      )}

      {step === 'intake' && me && (
        <section className="card onb-intake">
          <h1>Meet your coach</h1>
          <p className="muted">Your coach will interview you to build your profile, baselines, goals, and first-week plan. Answer naturally — one topic at a time.</p>
          <ChatBox
            kind="onboarding"
            placeholder="Say hi to start…"
            seed={`Hi ${me.user.name.split(' ')[0]}! I'm your AI coach. I'll ask you a few things to set up your training profile and first week. Ready? Tell me your sport and what you're training for.`}
          />
          <div className="onb-finish">
            <button className="link-btn" onClick={() => void finish()}>Finish &amp; go to dashboard →</button>
          </div>
        </section>
      )}
    </div>
  )
}
