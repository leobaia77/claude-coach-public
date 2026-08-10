import { useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { signIn, signUp } from '../authClient'

export function Login() {
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr('')
    setBusy(true)
    const { error } = await signIn.email({ email, password })
    setBusy(false)
    if (error) setErr(error.message || 'sign-in failed')
    else nav('/')
  }

  return (
    <AuthShell title="Sign in to your coach">
      <form onSubmit={submit} className="auth-form">
        <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {err && <div className="auth-err">{err}</div>}
        <button type="submit" disabled={busy}>{busy ? '…' : 'Sign in'}</button>
      </form>
      <div className="auth-alt">
        Have an invite? <Link to="/signup">Create your account</Link>
      </div>
    </AuthShell>
  )
}

export function Signup() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [inviteCode, setInviteCode] = useState(params.get('code') ?? '')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr('')
    if (password.length < 10) {
      setErr('Password must be at least 10 characters.')
      return
    }
    setBusy(true)
    // inviteCode is validated server-side by the better-auth before-hook.
    const { error } = await signUp.email({ name, email, password, inviteCode } as never)
    setBusy(false)
    if (error) setErr(error.message || 'sign-up failed')
    else nav('/onboarding')
  }

  return (
    <AuthShell title="Create your coach account">
      <form onSubmit={submit} className="auth-form">
        <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required />
        <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input type="password" placeholder="Password (10+ chars)" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <input placeholder="Invite code" value={inviteCode} onChange={(e) => setInviteCode(e.target.value.toUpperCase())} required />
        {err && <div className="auth-err">{err}</div>}
        <button type="submit" disabled={busy}>{busy ? '…' : 'Create account'}</button>
      </form>
      <div className="auth-alt">
        Already have an account? <Link to="/login">Sign in</Link>
      </div>
    </AuthShell>
  )
}

function AuthShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">🏋️ AI Coach</div>
        <h1>{title}</h1>
        {children}
      </div>
    </div>
  )
}
