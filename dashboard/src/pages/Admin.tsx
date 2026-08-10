import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAdminUsers, getAdminInvites, createInvite } from '../coachApi'

export function Admin() {
  const [users, setUsers] = useState<Array<Record<string, unknown>>>([])
  const [invites, setInvites] = useState<Array<Record<string, unknown>>>([])
  const [newInvite, setNewInvite] = useState<{ code: string; url: string } | null>(null)
  const [email, setEmail] = useState('')

  const load = () => {
    void getAdminUsers().then(setUsers).catch(() => {})
    void getAdminInvites().then(setInvites).catch(() => {})
  }
  useEffect(load, [])

  const make = async () => {
    const inv = await createInvite({ email: email.trim() || undefined, expiresInDays: 30 })
    setNewInvite(inv)
    setEmail('')
    load()
  }

  return (
    <div className="page">
      <div className="page-head">
        <h1>Admin</h1>
        <Link to="/">← Dashboard</Link>
      </div>

      <section className="card">
        <h2>Create invite</h2>
        <div className="row">
          <input placeholder="Lock to email (optional)" value={email} onChange={(e) => setEmail(e.target.value)} />
          <button onClick={() => void make()}>Generate invite</button>
        </div>
        {newInvite && (
          <div className="invite-created">
            <code>{newInvite.code}</code>
            <input readOnly value={newInvite.url} onFocus={(e) => e.target.select()} />
          </div>
        )}
      </section>

      <section className="card">
        <h2>Invites ({invites.length})</h2>
        <table className="admin-table">
          <thead><tr><th>Code</th><th>Email lock</th><th>Used</th></tr></thead>
          <tbody>
            {invites.map((i) => (
              <tr key={String(i.id)}>
                <td><code>{String(i.code)}</code></td>
                <td>{i.email ? String(i.email) : '—'}</td>
                <td>{i.usedBy ? '✓' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Users ({users.length})</h2>
        <table className="admin-table">
          <thead><tr><th>Email</th><th>Role</th><th>Stage</th><th>Integrations</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={String(u.id)}>
                <td>{String(u.email)}</td>
                <td>{String(u.role)}</td>
                <td>{String(u.onboardingStage)}</td>
                <td>{String(u.integrations)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
